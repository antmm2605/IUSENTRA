from io import BytesIO
from pathlib import Path
import uuid
import pytest
from werkzeug.datastructures import FileStorage
from tests.test_condivisioni_sql_repository import SQLFactory
from pct.email_mailbox_repository import EmailMailboxRepository
from pct.email_sql_client import GestioneEmailSQL
from pct.ordinary_local_smtp import LocalSmtpCommands, LocalSmtpConflict

@pytest.fixture
def setup():
    factory = SQLFactory('sqlite')
    tenant = 'studio-a'
    root = Path(factory.temp.name)/tenant
    path = root/'email'/'ordinaria.json'
    repo = EmailMailboxRepository(factory.new(),tenant,'ordinary',path)
    repo.ensure_schema();repo.initialize({},source_of_truth='sqlite')
    def mailbox(actor='avvocato', other_tenant=tenant):
        return GestioneEmailSQL(str(path),studio_db=factory.new(),tenant_key=other_tenant,
            mailbox_kind='ordinary',tenant_root=root,actor_key=actor,load_catalog=False)
    yield factory, mailbox
    factory.close()

def prepare(commands, command):
    return commands.prepare(command,sender='studio@example.test',recipients='cliente@example.test',
        subject='Documento',body='Testo',uploads=[FileStorage(stream=BytesIO(b'documento originale'),filename='atto.pdf')])

def test_confirm_is_atomic_idempotent_and_attachment_is_readable(setup):
    factory, make = setup
    mailbox=make();cmd=LocalSmtpCommands(mailbox,'avvocato');key=uuid.uuid4().hex
    payload=prepare(cmd,key)
    assert len(payload['attachments'])==1
    assert mailbox.repository.load()=={}
    cmd.confirm(key,message_id='<test@example.test>')
    LocalSmtpCommands(make(),'avvocato').confirm(key,message_id='<test@example.test>')
    rows=make().repository.load()
    assert len(rows)==1
    msg=make().get_readonly(next(iter(rows)))
    assert mailbox.percorso_allegato(msg,0).read_bytes()==b'documento originale'
    assert msg.message_id=='<test@example.test>'
    assert msg.cartella=='INVIATI'
    with pytest.raises(LocalSmtpConflict):cmd.confirm(key,message_id='<other@example.test>')

def test_same_command_cannot_dispatch_twice_after_reload(setup):
    _,make=setup;key=uuid.uuid4().hex
    prepare(LocalSmtpCommands(make(),'avvocato'),key)
    with pytest.raises(LocalSmtpConflict):prepare(LocalSmtpCommands(make(),'avvocato'),key)
    assert make().repository.load()=={}

def test_other_actor_cannot_confirm_and_missing_proof_is_not_sent(setup):
    _,make=setup;key=uuid.uuid4().hex
    prepare(LocalSmtpCommands(make(),'avvocato'),key)
    with pytest.raises(LocalSmtpConflict):LocalSmtpCommands(make('altro'),'altro').confirm(key,message_id='<test@example.test>')
    with pytest.raises(ValueError):LocalSmtpCommands(make(),'avvocato').confirm(key,message_id='')
    assert make().repository.load()=={}

def test_mailbox_insert_failure_rolls_back_sent_state(setup,monkeypatch):
    _,make=setup;mailbox=make();cmd=LocalSmtpCommands(mailbox,'avvocato');key=uuid.uuid4().hex
    prepare(cmd,key)
    def fail(*a,**k):raise RuntimeError('errore controllato')
    monkeypatch.setattr(mailbox.repository,'_audit',fail)
    with pytest.raises(RuntimeError):cmd.confirm(key,message_id='<test@example.test>')
    assert make().repository.load()=={}
    LocalSmtpCommands(make(),'avvocato').confirm(key,message_id='<test@example.test>')
    assert len(make().repository.load())==1

def test_ordinary_bridge_reports_pre_submission_failure_and_partial_refusal():
    import smtplib
    from tests.test_local_pec_bridge import _FakeSmtp, _payload
    from local_signer_mod.pec_bridge import send_pec_local
    class LoginFailure(_FakeSmtp):
        def login(self,*a):raise smtplib.SMTPAuthenticationError(535,b'controlled')
    result=send_pec_local(_payload(ordinary_email=True,to='client@example.test',subject='Test'),smtp_ssl_factory=LoginFailure)
    assert result['ok'] is False
    assert result['submission_started'] is False
    class Partial(_FakeSmtp):
        def send_message(self,*a,**kw):return {'refused@example.test':(550,b'controlled')}
    result=send_pec_local(_payload(ordinary_email=True,to=['ok@example.test','refused@example.test'],subject='Test'),smtp_ssl_factory=Partial)
    assert result['ok'] is False
    assert result['submission_started'] is True
    assert 'parziale' in result['messaggio']

def test_ordinary_api_to_local_smtp_to_sent_attachment(setup,tmp_path,monkeypatch):
    import importlib
    from tests.test_applicazioni import _cfg_web,_crea_operatore,_login
    from web.app import create_app
    from pct.messaggi import ConfigMessaggistica,ConfigEmail,GestioneMessaggi
    from tests.test_local_pec_bridge import _FakeSmtp
    from local_signer_mod.pec_bridge import send_pec_local
    routes=importlib.import_module('web.blueprints.email_ordinaria')
    _,make=setup
    app=create_app(_cfg_web(tmp_path/'app'));_crea_operatore(app)
    monkeypatch.setattr(routes,'_get_gestore',lambda **kw:make())
    config=ConfigMessaggistica(email=ConfigEmail(smtp_host='smtp.example.test',smtp_port=465,
        username='studio@example.test',password='fake-test-password',use_tls=False,mittente_email='studio@example.test'))
    monkeypatch.setattr(routes,'_messaggi_config_da_smtp',lambda:config)
    def forbidden(*a,**kw):raise AssertionError('SMTP server non consentito')
    monkeypatch.setattr(GestioneMessaggi,'invia_email',forbidden)
    with app.test_client() as client:
        _login(client)
        prepared=client.post('/email-ordinaria/scrivi',data={'a':'cliente@example.test','oggetto':'Test invio',
            'corpo':'Contenuto','local_command_id':uuid.uuid4().hex,'allegati':(BytesIO(b'allegato intatto'),'atto.pdf')},
            headers={'Accept':'application/json'})
        assert prepared.status_code==200,prepared.get_json()
        body=prepared.get_json();assert body['local_signer_required'] is True
        assert prepared.headers['Cache-Control']=='private, no-store'
        assert make().repository.load()=={}
        sent=send_pec_local(body['local_payload'],smtp_ssl_factory=_FakeSmtp)
        assert sent['ok'] is True
        assert list(_FakeSmtp.instances[-1].sent[0][0].iter_attachments())[0].get_payload(decode=True)==b'allegato intatto'
        receipt={**sent,'confirmation_token':body['confirmation_token']}
        for _ in range(2):
            confirmed=client.post('/email-ordinaria/scrivi/conferma-locale',json=receipt)
            assert confirmed.status_code==200,confirmed.get_json()
        rows=make().repository.load();assert len(rows)==1
        message=make().get_readonly(next(iter(rows)))
        assert make().percorso_allegato(message,0).read_bytes()==b'allegato intatto'
        forged=client.post('/email-ordinaria/scrivi/conferma-locale',json={**receipt,'confirmation_token':'forged'})
        assert forged.status_code==409

def test_same_command_is_isolated_between_studios(setup):
    factory,make=setup;key=uuid.uuid4().hex
    prepare(LocalSmtpCommands(make(),'avvocato'),key)
    root=Path(factory.temp.name)/'studio-b';path=root/'email'/'ordinaria.json'
    repo=EmailMailboxRepository(factory.new(),'studio-b','ordinary',path)
    repo.initialize({},source_of_truth='sqlite')
    other=GestioneEmailSQL(str(path),studio_db=factory.new(),tenant_key='studio-b',mailbox_kind='ordinary',tenant_root=root,load_catalog=False)
    commands=LocalSmtpCommands(other,'avvocato')
    with pytest.raises(LocalSmtpConflict):commands.confirm(key,message_id='<a@example.test>')
    prepare(commands,key);commands.confirm(key,message_id='<b@example.test>')
    assert make().repository.load()=={}
    assert len(other.repository.load())==1
