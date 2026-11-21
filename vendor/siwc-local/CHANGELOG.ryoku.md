# Alterações locais (Ryoku)

Arquivos alterados em relação ao commit pinado do DevKit, para integração via `file:`:

- `package.json` — `private: false`; scripts de build locais; `typescript` / `@types/node` como devDependencies
- `tsconfig.json` — compilação autônoma (sem `extends` do monorepo)

Código-fonte em `src/` permanece o do upstream no commit de `PIN.txt`, salvo necessidade futura marcada aqui.
