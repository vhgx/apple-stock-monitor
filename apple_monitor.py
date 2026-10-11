#!/usr/bin/env python3
"""
Apple Store Availability Monitor & Email Notifier
-------------------------------------------------
Monitora o estoque de retirada em lojas físicas da Apple em NY (Zip 10001)
e envia alertas por e-mail quando o produto estiver disponível.
"""

import sys
import os
import json
import time
import argparse
import smtplib
import http.cookiejar
import urllib.request
import urllib.parse
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Tenta carregar python-dotenv se estiver instalado
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # Parser manual simples de .env caso python-dotenv não esteja instalado
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

# Configurações Padrão
PART_NUMBER = os.environ.get("PART_NUMBER", "MJWA4LL/A")
PRODUCT_NAME = os.environ.get("PRODUCT_NAME", "iPhone 18 Pro Max 512GB Burgundy")
ZIP_CODE = os.environ.get("ZIP_CODE", "10001")

SMTP_SERVER = os.environ.get("SMTP_SERVER", "smtp-mail.outlook.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
EMAIL_SENDER = os.environ.get("EMAIL_SENDER", "")
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD", "")
EMAIL_RECEIVER = os.environ.get("EMAIL_RECEIVER", "")

CHECK_INTERVAL_MINUTES = int(os.environ.get("CHECK_INTERVAL_MINUTES", "5"))
STATE_FILE = os.path.join(os.path.dirname(__file__), "stock_state.json")

# Cores no terminal ANSI
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


class AppleStockChecker:
    def __init__(self, part_number: str, zip_code: str):
        self.part_number = part_number
        self.zip_code = zip_code
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        self._warmup_done = False

    def _warmup_session(self):
        """Gera cookies de sessão válidos para evitar bloqueios da Akamai/Apple."""
        if self._warmup_done:
            return
        warmup_url = "https://www.apple.com/shop/buy-iphone"
        req = urllib.request.Request(
            warmup_url,
            headers={
                **self.headers,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        try:
            with self.opener.open(req, timeout=15) as resp:
                if resp.status == 200:
                    self._warmup_done = True
        except Exception as e:
            # Continua mesmo se o warmup falhar, pois o endpoint pode responder
            pass

    def check_availability(self):
        """Consulta as lojas da Apple para o Zip Code informado."""
        self._warmup_session()
        
        encoded_part = urllib.parse.quote(self.part_number)
        url = f"https://www.apple.com/shop/retail/pickup-message?parts.0={encoded_part}&location={self.zip_code}"
        
        req = urllib.request.Request(
            url,
            headers={
                **self.headers,
                "Accept": "application/json",
                "Referer": "https://www.apple.com/shop/buy-iphone",
            },
        )

        try:
            with self.opener.open(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"{RED}[ERRO]{RESET} Falha ao consultar API da Apple: {e}")
            return []

        stores = data.get("body", {}).get("stores", [])
        results = []

        for store in stores:
            parts = store.get("partsAvailability", {}).get(self.part_number, {})
            pickup_display = parts.get("pickupDisplay", "unavailable")
            pickup_quote = parts.get("pickupSearchQuote", "Indisponível")
            
            is_available = (pickup_display.lower() == "available")

            results.append({
                "storeNumber": store.get("storeNumber"),
                "storeName": store.get("storeName"),
                "city": store.get("city"),
                "state": store.get("state"),
                "distance": store.get("storeDistanceWithUnit", "N/A"),
                "is_available": is_available,
                "pickup_display": pickup_display,
                "pickup_quote": pickup_quote,
                "product_title": parts.get("storePickupProductTitle", PRODUCT_NAME),
                "buy_url": f"https://www.apple.com/shop/buy-iphone"
            })

        return results


def send_email_alert(available_stores, is_test=False):
    """Envia alerta por e-mail com a lista de lojas disponíveis."""
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECEIVER:
        print(f"{YELLOW}[AVISO]{RESET} Credenciais de e-mail não configuradas no .env. Alerta não enviado.")
        return False

    msg = MIMEMultipart("alternative")
    prefix = "[TESTE] " if is_test else "🚨 [DISPONÍVEL] "
    msg["Subject"] = f"{prefix}Apple Store NY: {PRODUCT_NAME} em {len(available_stores)} loja(s)!"
    msg["From"] = f"Apple Stock Bot <{EMAIL_SENDER}>"
    msg["To"] = EMAIL_RECEIVER

    now_str = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")

    # Itens de loja em HTML
    store_rows = ""
    for store in available_stores:
        store_rows += f"""
        <tr style="border-bottom: 1px solid #e0e0e0;">
            <td style="padding: 12px; font-weight: bold; color: #1d1d1f;">{store['storeName']}</td>
            <td style="padding: 12px; color: #515154;">{store['distance']}</td>
            <td style="padding: 12px; color: #0071e3; font-weight: bold;">{store['pickup_quote']}</td>
        </tr>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f5f5f7; margin: 0; padding: 20px; }}
        .card {{ background-color: #ffffff; border-radius: 12px; max-width: 600px; margin: 0 auto; padding: 28px; box-shadow: 0 4px 14px rgba(0,0,0,0.08); }}
        .header {{ border-bottom: 2px solid #0071e3; padding-bottom: 16px; margin-bottom: 20px; }}
        .badge {{ background-color: #34c759; color: white; padding: 4px 10px; border-radius: 6px; font-size: 13px; font-weight: bold; display: inline-block; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ text-align: left; background-color: #f5f5f7; padding: 10px; color: #86868b; font-size: 13px; }}
        .btn {{ display: inline-block; background-color: #0071e3; color: #ffffff !important; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: bold; margin-top: 15px; text-align: center; }}
        .footer {{ margin-top: 25px; font-size: 12px; color: #86868b; border-top: 1px solid #e0e0e0; padding-top: 12px; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="header">
          <span class="badge">ESTOQUE CONFIRMADO</span>
          <h2 style="margin: 10px 0 0 0; color: #1d1d1f;">{PRODUCT_NAME}</h2>
          <p style="margin: 4px 0 0 0; color: #86868b; font-size: 14px;">Part Number: <b>{PART_NUMBER}</b> | Zip: <b>{ZIP_CODE}</b></p>
        </div>
        
        <p style="color: #1d1d1f; font-size: 15px;">
          O produto foi encontrado para retirada imediata nas seguintes lojas físicas da Apple em NY:
        </p>

        <table>
          <thead>
            <tr>
              <th>Loja</th>
              <th>Distância</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {store_rows}
          </tbody>
        </table>

        <div style="text-align: center;">
          <a href="https://www.apple.com/shop/buy-iphone" class="btn">
            Abrir Apple Store e Reservar Agora
          </a>
        </div>

        <div class="footer">
          Checado automaticamente em {now_str}.<br>
          Este e-mail é gerado automaticamente pelo seu monitor local de disponibilidade.
        </div>
      </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print(f"{GREEN}[SUCESSO]{RESET} Alerta enviado por e-mail para: {EMAIL_RECEIVER}")
        return True
    except Exception as e:
        print(f"{RED}[ERRO]{RESET} Falha ao conectar ao servidor SMTP: {e}")
        return False


def send_heartbeat_email(stores):
    """Envia o e-mail diário de confirmação 'Produto Apple Checado'."""
    if not EMAIL_SENDER or not EMAIL_PASSWORD or not EMAIL_RECEIVER:
        print(f"{YELLOW}[AVISO]{RESET} Credenciais de e-mail não configuradas no .env. Aviso não enviado.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Produto Apple Checado: Monitor Ativo (Status Diário)"
    msg["From"] = f"Apple Stock Bot <{EMAIL_SENDER}>"
    msg["To"] = EMAIL_RECEIVER

    now_str = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
    available_stores = [s for s in stores if s.get("is_available")]
    total_stores = len(stores)

    if available_stores:
        status_banner = f'<span style="background-color: #34c759; color: white; padding: 5px 12px; border-radius: 6px; font-weight: bold; font-size: 13px;">ESTOQUE DISPONÍVEL EM {len(available_stores)} LOJA(S)</span>'
        status_text = f"O produto está disponível para retirada em <b>{len(available_stores)}</b> loja(s) de NY!"
    else:
        status_banner = '<span style="background-color: #0071e3; color: white; padding: 5px 12px; border-radius: 6px; font-weight: bold; font-size: 13px;">MONITOR 100% ATIVO • ESGOTADO</span>'
        status_text = "Nenhuma loja com estoque imediato no momento. O script continua ativo checando a cada ciclo e avisará no mesmo instante em que houver estoque."

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f5f5f7; margin: 0; padding: 20px; }}
        .card {{ background-color: #ffffff; border-radius: 12px; max-width: 600px; margin: 0 auto; padding: 28px; box-shadow: 0 4px 14px rgba(0,0,0,0.08); }}
        .header {{ border-bottom: 2px solid #0071e3; padding-bottom: 16px; margin-bottom: 20px; }}
        .footer {{ margin-top: 25px; font-size: 12px; color: #86868b; border-top: 1px solid #e0e0e0; padding-top: 12px; }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="header">
          {status_banner}
          <h2 style="margin: 12px 0 0 0; color: #1d1d1f;">Produto Apple Checado</h2>
          <p style="margin: 4px 0 0 0; color: #86868b; font-size: 14px;">Relatório diário de funcionamento do monitor</p>
        </div>

        <p style="color: #1d1d1f; font-size: 15px; line-height: 1.5;">
          Olá! Este é o seu aviso diário confirmando que o monitoramento do <b>{PRODUCT_NAME}</b> está rodando normalmente no GitHub Actions.
        </p>

        <div style="background-color: #f5f5f7; border-radius: 8px; padding: 16px; margin: 20px 0;">
          <p style="margin: 4px 0; color: #1d1d1f; font-size: 14px;"><b>Produto:</b> {PRODUCT_NAME} ({PART_NUMBER})</p>
          <p style="margin: 4px 0; color: #1d1d1f; font-size: 14px;"><b>Região:</b> Nova York (ZIP {ZIP_CODE})</p>
          <p style="margin: 4px 0; color: #1d1d1f; font-size: 14px;"><b>Lojas consultadas:</b> {total_stores} Apple Stores de NY</p>
          <p style="margin: 4px 0; color: #1d1d1f; font-size: 14px;"><b>Situação:</b> {status_text}</p>
        </div>

        <p style="color: #515154; font-size: 13px;">
          <i>Lembrete: você <b>só</b> receberá outros e-mails se alguma loja tiver o produto em estoque para retirada imediata.</i>
        </p>

        <div class="footer">
          Verificação executada com sucesso em {now_str}.
        </div>
      </div>
    </body>
    </html>
    """

    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        print(f"{GREEN}[SUCESSO]{RESET} Aviso diário 'Produto Apple Checado' enviado para: {EMAIL_RECEIVER}")
        return True
    except Exception as e:
        print(f"{RED}[ERRO]{RESET} Falha ao conectar ao servidor SMTP: {e}")
        return False


def load_previous_state():
    """Lê o histórico de lojas notificadas."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_current_state(state):
    """Grava o histórico de lojas notificadas."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"{YELLOW}[AVISO]{RESET} Não foi possível gravar {STATE_FILE}: {e}")


def print_status_table(stores):
    """Exibe o status de todas as lojas de forma organizada no console."""
    print(f"\n{BOLD}{CYAN}=== STATUS DE DISPONIBILIDADE NA APPLE STORE (NY - {ZIP_CODE}) ==={RESET}")
    print(f"Produto: {BOLD}{PRODUCT_NAME}{RESET} (SKU: {PART_NUMBER})")
    print(f"Horário: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    print(f"{'Loja':<24} | {'Distância':<10} | {'Status':<15} | {'Detalhes'}")
    print("-" * 75)
    
    available_count = 0
    for s in stores:
        if s["is_available"]:
            status_str = f"{GREEN}DISPONÍVEL{RESET}"
            available_count += 1
        else:
            status_str = f"{RED}Esgotado{RESET}"
        print(f"{s['storeName']:<24} | {s['distance']:<10} | {status_str:<24} | {s['pickup_quote']}")

    print("-" * 75)
    if available_count > 0:
        print(f"{GREEN}{BOLD}🎉 Total disponível: {available_count} loja(s)!{RESET}\n")
    else:
        print(f"{YELLOW}Nenhuma loja com estoque no momento.{RESET}\n")


def perform_check(checker: AppleStockChecker, verbose: bool = False):
    """Executa uma verificação completa e dispara alertas se houver novidades."""
    now_str = datetime.now().strftime("%H:%M:%S")
    print(f"[{now_str}] Consultando Apple Stores para Zip {ZIP_CODE}...")
    
    stores = checker.check_availability()
    if not stores:
        print(f"{YELLOW}[AVISO]{RESET} Nenhuma resposta obtida da Apple. Tentando novamente na próxima rodada.")
        return

    available_stores = [s for s in stores if s["is_available"]]
    
    if verbose:
        print_status_table(stores)

    prev_state = load_previous_state()
    prev_notified_ids = set(prev_state.get("notified_store_ids", []))
    current_available_ids = {s["storeNumber"] for s in available_stores}

    if available_stores:
        print(f"{GREEN}{BOLD}[ESTOQUE ENCONTRADO]{RESET} {len(available_stores)} loja(s) disponível(is)!")
        for s in available_stores:
            print(f"  -> {s['storeName']} ({s['distance']}): {s['pickup_quote']}")

        # Envia e-mail se houver novas lojas que ainda não foram notificadas
        new_stores = [s for s in available_stores if s["storeNumber"] not in prev_notified_ids]
        if new_stores:
            print(f"{CYAN}[ALERTA]{RESET} Novas lojas disponíveis detectadas. Enviando e-mail...")
            send_email_alert(available_stores)
        else:
            print(f"{CYAN}[INFO]{RESET} O estoque dessas lojas já foi notificado no alerta anterior.")
    else:
        print(f"[{now_str}] Nenhuma loja com retirada imediata disponível no momento.")

    # Atualiza o arquivo de estado
    save_current_state({
        "last_checked": datetime.now().isoformat(),
        "notified_store_ids": list(current_available_ids)
    })


def main():
    parser = argparse.ArgumentParser(description="Apple Store Availability Monitor & Email Notifier")
    parser.add_argument("--status", action="store_true", help="Mostra a tabela com o status atual de todas as lojas")
    parser.add_argument("--check", action="store_true", help="Executa uma única verificação (ideal para cron / agendador)")
    parser.add_argument("--loop", action="store_true", help="Executa continuamente a cada N minutos")
    parser.add_argument("--interval", type=int, default=CHECK_INTERVAL_MINUTES, help="Intervalo em minutos para o modo --loop")
    parser.add_argument("--test-email", action="store_true", help="Testa o envio de e-mail com as credenciais configuradas")
    parser.add_argument("--heartbeat", action="store_true", help="Executa a checagem e envia o e-mail diário 'Produto Apple Checado'")
    parser.add_argument("--simulate-available", action="store_true", help="Simula lojas com estoque para testar o template de alerta")

    args = parser.parse_args()
    checker = AppleStockChecker(PART_NUMBER, ZIP_CODE)

    if args.heartbeat:
        print(f"[HEARTBEAT] Consultando status para envio do relatório diário 'Produto Apple Checado'...")
        stores = checker.check_availability()
        print_status_table(stores)
        send_heartbeat_email(stores)
        return

    if args.status:
        stores = checker.check_availability()
        print_status_table(stores)
        return

    if args.test_email:
        print(f"[TESTE] Enviando e-mail de teste para {EMAIL_RECEIVER}...")
        test_stores = [
            {"storeName": "Fifth Avenue", "distance": "1.8 mi", "pickup_quote": "Available Today (Simulação)"},
            {"storeName": "SoHo", "distance": "1.77 mi", "pickup_quote": "Available Today (Simulação)"}
        ]
        send_email_alert(test_stores, is_test=True)
        return

    if args.simulate_available:
        print(f"[SIMULAÇÃO] Testando fluxo de disponibilidade simulando Fifth Avenue e Grand Central...")
        test_stores = [
            {"storeNumber": "R095", "storeName": "Fifth Avenue", "distance": "1.8 mi", "pickup_quote": "Available Today"},
            {"storeNumber": "R415", "storeName": "Grand Central", "distance": "1.35 mi", "pickup_quote": "Available Today"}
        ]
        send_email_alert(test_stores, is_test=False)
        return

    if args.loop:
        interval_sec = max(60, args.interval * 60)
        print(f"{BOLD}{GREEN}Monitor iniciado em modo contínuo.{RESET}")
        print(f"Produto: {PRODUCT_NAME} ({PART_NUMBER})")
        print(f"Local: Zip {ZIP_CODE} | Intervalo: {args.interval} minuto(s)")
        print(f"Pressione Ctrl+C para encerrar.\n")
        try:
            while True:
                perform_check(checker, verbose=False)
                print(f"Aguardando {args.interval} minuto(s) até a próxima checagem...\n")
                time.sleep(interval_sec)
        except KeyboardInterrupt:
            print(f"\n{YELLOW}Monitor finalizado pelo usuário.{RESET}")
        return

    # Padrão: se nenhum argumento for passado ou for --check, executa uma verificação completa
    perform_check(checker, verbose=True)


if __name__ == "__main__":
    main()
