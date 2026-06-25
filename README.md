# Sistema Ponto REM

Sistema web para loja de tênis ortopédicos com painel interno, estoque por tamanho/cor, vendas e catálogo público.

## Acessos

- Painel: `/login`
- Catálogo público: `/catalogo`
- Usuário padrão: `admin`
- Senha padrão: `admin123`

Troque a senha nas variáveis do Coolify:

```env
SECRET_KEY=uma-chave-grande
ADMIN_USER=admin
ADMIN_PASSWORD=sua-senha-forte
DATA_DIR=/data
```

## Recursos

- Cadastro de produtos com foto, preço, custo, descrição e categoria
- Estoque por modelo, cor e tamanho
- Entrada, saída e ajuste de estoque
- Registro de venda com baixa automática
- Recibo de venda para impressão
- Dashboard com vendas do mês, estoque baixo, valor parado e mais vendidos
- Relatórios de receita, lucro estimado e tamanhos mais vendidos
- Catálogo público com filtros por busca, cor e tamanho
- Botão de WhatsApp no produto
- Configurações internas para nome da loja, texto do catálogo e WhatsApp

## Deploy no Coolify

1. Suba este projeto em um repositório GitHub.
2. No Coolify, crie um novo app usando Dockerfile ou Docker Compose.
3. Configure as variáveis de ambiente.
4. Configure volumes persistentes:
   - `/data`
   - `/app/static/uploads`
5. Faça o deploy.

## Observação importante

O banco SQLite fica em `/data/ponto_rem.db`. Para não perder dados em atualização, mantenha o volume `/data` persistente no Coolify.
