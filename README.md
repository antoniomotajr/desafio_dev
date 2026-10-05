# Mota Business Suite — Clean & Secure

Versão enxuta e revisada de segurança.

## Estrutura

```text
mota-business-suite-clean-secure/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── ABRIR_MOTA_SUITE.bat
├── iniciar_linux_mac.sh
├── templates/
│   └── index.html
└── static/
    ├── app.css
    ├── app.js
    ├── manifest.json
    ├── sw.js
    └── icons/
        ├── icon-192.png
        └── icon-512.png
```

Não existem vários `.bat` fazendo a mesma coisa.

## Windows — modo local recomendado

Dê duplo clique:

```text
ABRIR_MOTA_SUITE.bat
```

O servidor fica preso em:

```text
127.0.0.1:5000
```

Nesse modo, outros equipamentos da rede não conseguem acessar o sistema.

## Windows — celular/tablet na rede local

Abra o Prompt/PowerShell na pasta e execute:

```bat
ABRIR_MOTA_SUITE.bat rede
```

O programa gera um **token aleatório para aquela execução** e mostra uma URL como:

```text
http://192.168.0.20:5000/?token=xxxxxxxx
```

Use exatamente essa URL no celular/tablet.

O token muda a cada execução em modo rede.

## Linux/macOS

```bash
chmod +x iniciar_linux_mac.sh
./iniciar_linux_mac.sh
```

Por padrão, também usa somente `127.0.0.1`.

## Segurança aplicada

- servidor disponível apenas em `127.0.0.1` por padrão;
- modo LAN precisa ser ativado explicitamente;
- acesso LAN protegido por token;
- requests mutáveis exigem cabeçalho customizado;
- validação de `Origin` nas operações POST/PUT/DELETE;
- sem CORS aberto;
- limite de 1 MB por request;
- SQL parametrizado;
- limites de tamanho para textos;
- valores `NaN`/`Infinity` rejeitados;
- movimentação de estoque feita em transação SQLite;
- backup consistente pela API de backup do SQLite;
- headers de segurança:
  - CSP;
  - X-Frame-Options;
  - X-Content-Type-Options;
  - Referrer-Policy;
  - Permissions-Policy;
- proteção contra CSV Formula Injection;
- frontend não injeta dados cadastrados via `innerHTML`;
- service worker não armazena API, backup ou exportações;
- APIs/backup/CSV usam `Cache-Control: no-store`;
- `debug=False`;
- Waitress no lugar do servidor de desenvolvimento do Flask.

## Observação importante sobre PWA em celular

Browsers normalmente exigem **HTTPS** para instalar/service worker fora de `localhost`.

Assim:

- no próprio PC em `localhost`: instalação PWA pode funcionar;
- no celular usando `http://192.168.x.x`: o sistema funciona no navegador, mas a instalação PWA pode ser bloqueada;
- para PWA instalável em celular de forma correta, publique por **HTTPS**.

## Dados que NÃO devem ir ao Git

O `.gitignore` exclui:

- banco SQLite;
- backups;
- CSVs exportados;
- ambientes virtuais;
- `.env`;
- caches Python.

## Desenvolvedor

**Antonio (Junior) Mota**

Desenvolvedor Full Stack | PHP, Python, JS | APIs REST, Web, Visão Computacional & IA

- LinkedIn: https://www.linkedin.com/in/afmotajunior
- Portfólio: https://antoniomotajr.github.io/portfolio/
- GitHub: https://github.com/antoniomotajr
- Instagram: https://www.instagram.com/afmotajunior/
- E-mail: antoniomotajr@gmail.com


## Comissão configurável por produto

A versão final permite cadastrar a comissão individual de cada produto.

No cadastro/edição de produto agora existem:

- custo unitário;
- preço de venda;
- percentual de comissão.

O percentual pode ser definido pela empresa com base em:

- margem de lucro do produto;
- custos operacionais;
- práticas de mercado do setor.

### Regra de cálculo

Quando uma venda estiver vinculada a um produto com percentual cadastrado:

```text
comissão = valor da venda × percentual / 100
```

Exemplo:

```text
Venda: R$ 1.000,00
Comissão cadastrada: 3,5%
Comissão: R$ 35,00
```

O percentual utilizado é gravado na própria venda para preservar o histórico,
mesmo que a comissão do produto seja alterada posteriormente.

### Compatibilidade com o desafio original

A regra original continua disponível como fallback:

- abaixo de R$ 100,00: 0%;
- R$ 100,00 até R$ 499,99: 1%;
- a partir de R$ 500,00: 5%.

Se o produto não possuir comissão personalizada, o sistema aplica essa regra.


## Página Sobre

A página **Sobre** possui dois recursos adicionais:

### Visualização interna do README

O botão **Visualizar README** carrega o próprio `README.md` dentro de um modal
do sistema. O backend utiliza um caminho fixo para esse arquivo; nenhum caminho
informado pelo navegador é aceito.

### Possíveis evoluções

O botão **Possíveis evoluções** exibe um roadmap organizado por prioridade,
incluindo autenticação, auditoria, regras de comissão mais avançadas,
dashboard financeiro, relatórios, metas comerciais, PostgreSQL, API REST,
HTTPS e aplicativo mobile.


## Gráfico de vendedores e comissões

Na página **Vendas & Comissões** existe um painel de análise com três períodos:

- Semana atual;
- Mês atual;
- Ano atual.

O gráfico compara os vendedores pelo valor total de comissão no período e também
apresenta:

- total vendido;
- total de comissões;
- vendedor líder;
- quantidade de vendas por vendedor;
- valor vendido por vendedor.

O cálculo usa o percentual de comissão efetivamente gravado em cada venda.


## Acesso LAN sem token na URL

O modo de rede foi alterado para impedir que o segredo apareça na barra de
endereço, histórico do navegador, favoritos ou links compartilhados.

Execute:

```bat
ABRIR_MOTA_SUITE.bat rede
```

O computador mostra separadamente:

```text
Endereço:
http://192.168.0.20:5000

Código temporário:
xxxxxxxxxxxxxxxx
```

No celular/tablet:

1. abra apenas o endereço;
2. a tela **Acesso protegido** será exibida;
3. digite o código temporário;
4. após a autenticação, o sistema grava a autorização em cookie `HttpOnly`;
5. a URL continua limpa, sem segredo.

O cookie usa `SameSite=Strict` e expira em 8 horas.

Como o modo LAN local ainda usa HTTP, o cookie não pode usar a flag `Secure`.
Para publicação fora da rede doméstica, use HTTPS.


## Proteção de autoria

Esta distribuição contém três mecanismos de identificação:

1. marca d'água discreta na interface;
2. Build ID único: `MBS-2E52A5EAD317D703`;
3. fingerprint SHA-256: `2e52a5ead317d703ab9a7ef9abafd68c5ac99c781f8ddae60b19565b19e10555`.

Também existe o endpoint local:

```text
/api/assinatura-software
```

Ele informa o titular, Build ID e fingerprint desta versão.

Esses mecanismos são **evidência de autoria e integridade**, não DRM absoluto.
Quem possuir todo o código-fonte ainda pode tentar remover referências visuais.
Para distribuição comercial, combine isso com licença de uso, builds assinados,
controle de versões e, se necessário, ativação/licenciamento.
