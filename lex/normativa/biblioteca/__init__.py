"""Biblioteca «Codici e leggi» autoalimentata: riferimenti delle schede, acquisizione delle fonti mancanti.

- ``riferimenti``: dalla chiave di un atto (``dpr_396_2000``, ``reg_ue_2022_2065``) alla fonte ufficiale da cui scaricarlo;
- ``normattiva_akn``: download del testo vigente in Akoma Ntoso da Normattiva e conversione in righe JSONL;
- ``fabbisogno``: norme richieste dalle schede dei modelli d'atto e verifica della loro presenza in biblioteca;
- ``acquisizione``: scarica gli atti mancanti, controlla che contengano gli articoli richiesti e li importa
  con ``lex.normativa.consultazione.importa_fonti`` (backup automatico del database prima di scrivere).

Fonti ammesse: Normattiva (Istituto Poligrafico e Zecca dello Stato) e Ufficio delle pubblicazioni dell'UE, le stesse
accettate da ``importa_fonti``. Base: art. 20 CAD per integrita' e provenienza dei testi acquisiti.
"""
