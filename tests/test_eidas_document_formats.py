"""Regressione crittografica su campioni indipendenti EU DSS.

I certificati di test sono storici: qui si verifica integrità, non catena,
revoca, qualificazione eIDAS o validità temporale della firma.
"""

import base64
import copy
import hashlib
import io
import json
import zipfile
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
from lxml import etree


FIXTURES = Path(__file__).parent / "fixtures" / "eidas_formats"
DS = "http://www.w3.org/2000/09/xmldsig#"
XADES = "http://uri.etsi.org/01903/v1.3.2#"
SIGNED_PROPERTIES = "http://uri.etsi.org/01903#SignedProperties"
SHA256 = "http://www.w3.org/2001/04/xmlenc#sha256"
RSA_SHA256 = "http://www.w3.org/2001/04/xmldsig-more#rsa-sha256"
C14N = "http://www.w3.org/2001/10/xml-exc-c14n#"


def _decode(value: str) -> bytes:
    return base64.b64decode("".join(value.split()), validate=True)


def _verify_xades(xml: bytes, detached: dict[str, bytes] | None = None) -> None:
    root = etree.fromstring(xml, parser=etree.XMLParser(resolve_entities=False, no_network=True))
    signatures = root.findall(f".//{{{DS}}}Signature")
    assert len(signatures) == 1
    signature = signatures[0]
    signed_info = signature.find(f"{{{DS}}}SignedInfo")
    assert signed_info is not None
    assert signed_info.find(f"{{{DS}}}CanonicalizationMethod").get("Algorithm") == C14N
    assert signed_info.find(f"{{{DS}}}SignatureMethod").get("Algorithm") == RSA_SHA256
    refs = signed_info.findall(f"{{{DS}}}Reference")
    assert len(refs) == 2
    assert sum(ref.get("Type") == SIGNED_PROPERTIES for ref in refs) == 1
    for ref in refs:
        assert ref.find(f"{{{DS}}}DigestMethod").get("Algorithm") == SHA256
        uri = ref.get("URI")
        transforms = [t.get("Algorithm") for t in ref.findall(f"{{{DS}}}Transforms/{{{DS}}}Transform")]
        if uri == "":
            assert detached is None
            assert transforms == ["http://www.w3.org/TR/1999/REC-xpath-19991116", C14N]
            xpath = ref.find(f"{{{DS}}}Transforms/{{{DS}}}Transform/{{{DS}}}XPath")
            assert xpath is not None and xpath.text == "not(ancestor-or-self::ds:Signature)"
            target = copy.deepcopy(root)
            target.find(f".//{{{DS}}}Signature").getparent().remove(target.find(f".//{{{DS}}}Signature"))
            data = etree.tostring(target, method="c14n", exclusive=True)
        elif uri.startswith("#"):
            assert ref.get("Type") == SIGNED_PROPERTIES and transforms == [C14N]
            targets = root.xpath("//*[@Id=$id]", id=uri[1:])
            assert len(targets) == 1 and targets[0].tag == f"{{{XADES}}}SignedProperties"
            data = etree.tostring(targets[0], method="c14n", exclusive=True)
        else:
            assert detached is not None and not transforms and uri in detached
            data = detached[uri]
        actual = base64.b64encode(hashlib.sha256(data).digest()).decode("ascii")
        assert actual == "".join(ref.findtext(f"{{{DS}}}DigestValue").split())
    cert_text = signature.findtext(f"{{{DS}}}KeyInfo/{{{DS}}}X509Data/{{{DS}}}X509Certificate")
    cert = x509.load_der_x509_certificate(_decode(cert_text))
    cert.public_key().verify(
        _decode(signature.findtext(f"{{{DS}}}SignatureValue")),
        etree.tostring(signed_info, method="c14n", exclusive=True),
        padding.PKCS1v15(), hashes.SHA256(),
    )


def _verify_jades(jws: str) -> None:
    protected, payload, signature = jws.strip().split(".")
    header = json.loads(base64.urlsafe_b64decode(protected + "=="))
    assert header["alg"] == "RS256" and header["cty"] == "json"
    assert isinstance(header.get("x5c"), list) and header["x5c"]
    assert "sigT" in header.get("crit", [])
    cert_der = _decode(header["x5c"][0])
    thumbprint = base64.urlsafe_b64encode(hashlib.sha256(cert_der).digest()).rstrip(b"=").decode()
    assert header["x5t#S256"] == thumbprint
    json.loads(base64.urlsafe_b64decode(payload + "=="))
    cert = x509.load_der_x509_certificate(cert_der)
    cert.public_key().verify(
        base64.urlsafe_b64decode(signature + "=="),
        f"{protected}.{payload}".encode("ascii"),
        padding.PKCS1v15(), hashes.SHA256(),
    )


def _verify_asic(data: bytes, kind: str) -> None:
    with zipfile.ZipFile(io.BytesIO(data)) as container:
        names = container.namelist()
        assert len(names) == len(set(names))
        assert names.count("mimetype") == 1
        assert container.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        assert container.read("mimetype") == f"application/vnd.etsi.asic-{kind}+zip".encode()
        signature_files = [n for n in names if n.startswith("META-INF/signatures") and n.endswith(".xml")]
        assert len(signature_files) == 1
        payload = {n: container.read(n) for n in names if not n.startswith("META-INF/") and n != "mimetype"}
        assert payload and all("/" not in n and ".." not in n for n in payload)
        if kind == "e":
            manifest = etree.fromstring(container.read("META-INF/manifest.xml"))
            listed = {entry.get("{urn:oasis:names:tc:opendocument:xmlns:manifest:1.0}full-path")
                      for entry in manifest if entry.get("{urn:oasis:names:tc:opendocument:xmlns:manifest:1.0}full-path") != "/"}
            assert listed == set(payload)
        _verify_xades(container.read(signature_files[0]), payload)


def test_xades_b_signed_properties_and_document_digest():
    xml = (FIXTURES / "xades-b.xml").read_bytes()
    _verify_xades(xml)
    with pytest.raises(AssertionError):
        _verify_xades(xml.replace(b"Hello World !", b"Hello World ?"))


def test_jades_b_x5c_and_signature():
    jws = (FIXTURES / "jades-b.json").read_text(encoding="utf-8")
    _verify_jades(jws)
    parts = jws.strip().split(".")
    payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))
    assert payload
    altered = base64.urlsafe_b64encode(b'{"altered":true}').rstrip(b"=").decode()
    with pytest.raises(InvalidSignature):
        _verify_jades(f"{parts[0]}.{altered}.{parts[2]}")
    header = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))
    del header["x5c"]
    missing_x5c = base64.urlsafe_b64encode(json.dumps(header).encode()).rstrip(b"=").decode()
    with pytest.raises(AssertionError):
        _verify_jades(f"{missing_x5c}.{parts[1]}.{parts[2]}")


@pytest.mark.parametrize("kind,fixture", [("e", "asic-e-xades.asice"), ("s", "asic-s-xades.asics")])
def test_asic_xades_container_and_tampered_payload(kind, fixture):
    original = (FIXTURES / fixture).read_bytes()
    _verify_asic(original, kind)
    source = zipfile.ZipFile(io.BytesIO(original))
    altered = io.BytesIO()
    with zipfile.ZipFile(altered, "w") as output:
        for member in source.infolist():
            content = source.read(member.filename)
            output.writestr(member, content + b"altered" if member.filename == "test.text" else content)
    with pytest.raises(AssertionError):
        _verify_asic(altered.getvalue(), kind)
