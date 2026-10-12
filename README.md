# Apple Store Stock Monitor & Email Notifier 🍎

Monitor automatizado de estoque para retirada nas lojas físicas da Apple em Nova York (ZIP `10001`), com alertas imediatos por e-mail via SMTP.

Configurado especificamente para:
- **Modelo:** iPhone 18 Pro Max
- **Cor:** Burgundy
- **Capacidade:** 512GB
- **Part Number (SKU oficial):** `MJWA4LL/A`
- **Região monitorada:** Manhattan e arredores (Fifth Avenue, Grand Central, SoHo, West 14th St, Upper West/East Side, World Trade Center, Williamsburg, Brooklyn, etc.)

---

## 🚀 Como Funciona

1. O script executa um aquecimento de sessão para obter cookies legítimos da Apple e evitar bloqueios da CDN (Akamai).
2. Consulta o endpoint de disponibilidade de retirada (`/shop/retail/pickup-message`) para o SKU `MJWA4LL/A` e CEP `10001`.
3. Analisa o status `pickupDisplay` de cada uma das 12 lojas da região.
4. Quando uma loja mudar para `available`, dispara um e-mail formatado em HTML com link direto de reserva.
5. Mantém um arquivo local de estado (`stock_state.json`) para evitar envio repetido de e-mails para lojas já notificadas.

---

## 🛠️ Passo a Passo de Configuração

### 1. Criar o arquivo de credenciais `.env`
Copie o modelo de exemplo:
```bash
cp .env.example .env
```

Abra o `.env` e preencha suas informações:
```ini
PART_NUMBER=MJWA4LL/A
PRODUCT_NAME=iPhone 18 Pro Max 512GB Burgundy
ZIP_CODE=10001

SMTP_SERVER=smtp-mail.outlook.com
SMTP_PORT=587
EMAIL_SENDER=seu_email@exemplo.com
EMAIL_PASSWORD=sua_senha_de_app_microsoft
EMAIL_RECEIVER=seu_email@exemplo.com
```

### 2. Gerar a Senha de Aplicativo na Conta Microsoft (Outlook / Live)
Se você possui **Verificação em Duas Etapas** ativada na sua conta Microsoft:
1. Acesse: [https://account.live.com/proofs/manage/additional](https://account.live.com/proofs/manage/additional) (Segurança Adicional da Conta Microsoft).
2. Role a página até a seção **Senhas de aplicativo** (App passwords).
3. Clique em **Criar uma nova senha de aplicativo**.
4. Uma senha aleatória será gerada (ex: `abcd-efgh-ijkl-mnop`).
5. Cole essa senha no campo `EMAIL_PASSWORD` do seu `.env`.

*(Nota: Se você não tiver verificação em duas etapas ativada, pode usar sua senha habitual do Outlook/Live, embora a senha de app seja sempre a opção recomendada e mais segura).*

---

## 💻 Comandos e Testes

O script não depende de nenhuma biblioteca externa obrigatória (funciona direto com o Python 3 nativo do macOS).

### 1. Ver o status atual de todas as lojas no terminal
```bash
python3 apple_monitor.py --status
```
Exemplo de saída:
```text
=== STATUS DE DISPONIBILIDADE NA APPLE STORE (NY - 10001) ===
Produto: iPhone 18 Pro Max 512GB Burgundy (SKU: MJWA4LL/A)

Loja                     | Distância  | Status          | Detalhes
---------------------------------------------------------------------------
West 14th Street         | 0.66 mi    | Esgotado        | Unavailable for Pickup
Grand Central            | 1.35 mi    | Esgotado        | Unavailable for Pickup
SoHo                     | 1.77 mi    | Esgotado        | Unavailable for Pickup
Fifth Avenue             | 1.8 mi     | Esgotado        | Unavailable for Pickup
Upper West Side          | 1.99 mi    | Esgotado        | Unavailable for Pickup
Upper East Side          | 2.55 mi    | Esgotado        | Unavailable for Pickup
World Trade Center       | 2.72 mi    | Esgotado        | Unavailable for Pickup
Williamsburg             | 3.29 mi    | Esgotado        | Unavailable for Pickup
...
```

### 2. Testar o envio de e-mail (validação de credenciais)
```bash
python3 apple_monitor.py --test-email
```

### 3. Simular disponibilidade (testa o layout do e-mail de alerta)
```bash
python3 apple_monitor.py --simulate-available
```

### 4. Rodar uma única checagem
```bash
python3 apple_monitor.py --check
```

---

## 🔄 Como Deixar Rodando Automaticamente

### Opção A: Em segundo plano no Mac
Para deixar o script checando a cada 5 minutos:
```bash
nohup ./run_loop.sh > monitor.log 2>&1 &
```
Para parar:
```bash
pkill -f "apple_monitor.py"
```

### Opção B: No agendador do Mac (`crontab`)
Para rodar a cada 5 minutos automaticamente:
```bash
crontab -e
```
Adicione a linha:
```cron
*/5 * * * * cd /Users/vitorh/Documents/antigravity/fervent-fermi && /usr/bin/python3 apple_monitor.py --check >> cron_monitor.log 2>&1
```

### Opção C: 100% Grátis na Nuvem (GitHub Actions)
Já deixamos configurado o arquivo `.github/workflows/stock_check.yml`.
1. Suba este projeto para um repositório **privado** no seu GitHub.
2. No GitHub, vá em **Settings** > **Secrets and variables** > **Actions** > **New repository secret**.
3. Crie os segredos:
   - `EMAIL_SENDER`: seu Gmail
   - `EMAIL_PASSWORD`: sua Senha de App do Google (16 dígitos)
   - `EMAIL_RECEIVER`: seu e-mail de destino
4. O GitHub Actions executará o script a cada 10 minutos na nuvem sem precisar do seu Mac ligado!
