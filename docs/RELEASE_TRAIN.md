# Release Train

## Branching pratico
- `main` o branch di release stabile
- feature branch corte
- hotfix branch separati

## Flusso consigliato
1. feature branch
2. PR
3. CI verde
4. merge su ramo stabile
5. smoke deploy
6. release tag
7. changelog

## Hotfix
Per bug critici:
- branch `hotfix/...`
- patch minima
- smoke rapido
- merge e tag dedicato

## Regola base
Mai rilasciare senza:
- CI verde
- smoke healthcheck
- verifica login
- verifica route critiche
- verifica storage persistente
