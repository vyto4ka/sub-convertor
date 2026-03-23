import base64
import asyncio
import binascii
import httpx
import os
from fastapi import FastAPI, Response

app = FastAPI()

SOURCES_FILE = "/app/data/sources.txt"
# Пути к сертификатам внутри контейнера
CERT_FILE = "/app/certs/fullchain.pem"
KEY_FILE = "/app/certs/privkey.pem"

HEADERS = {"User-Agent": "v2rayN/6.31"} 

def decode_base64(text: str) -> str:
    text = text.strip()
    text += "=" * ((4 - len(text) % 4) % 4)
    try:
        # Пытаемся декодировать, если это Base64 подписка
        decoded = base64.b64decode(text).decode('utf-8', errors='ignore')
        return decoded
    except (binascii.Error, ValueError):
        return text

async def fetch_subscription(client: httpx.AsyncClient, url: str) -> list[str]:
    links = []
    try:
        resp = await client.get(url, timeout=10.0)
        resp.raise_for_status()
        
        text = resp.text
        # Если в ответе нет протоколов (vless:// и т.д.), скорее всего это Base64
        if "://" not in text:
            text = decode_base64(text)
            
        for sub_line in text.splitlines():
            sub_line = sub_line.strip()
            if sub_line and not sub_line.startswith(("#", "//")):
                links.append(sub_line)
    except Exception as e:
        print(f"[!] Ошибка при скачивании {url}: {e}")
    
    return links

async def get_all_links():
    """Общая логика сбора ссылок из файла и по URL"""
    combined_links = []
    http_urls = []
    
    try:
        with open(SOURCES_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                
                if line.startswith(("http://", "https://")):
                    http_urls.append(line)
                else:
                    combined_links.append(line)
    except FileNotFoundError:
        return None

    async with httpx.AsyncClient(verify=False, headers=HEADERS) as client:
        tasks = [fetch_subscription(client, url) for url in http_urls]
        results = await asyncio.gather(*tasks)
        
        for sub_links in results:
            combined_links.extend(sub_links)
    
    # Убираем дубликаты
    return list(dict.fromkeys(combined_links))

@app.get("/my-secret-sub")
async def get_subscription_encoded():
    """Версия с Base64 (стандартная для многих клиентов)"""
    links = await get_all_links()
    if links is None:
        return Response(content="sources.txt not found", status_code=404)
        
    final_text = "\n".join(links)
    encoded_bytes = base64.b64encode(final_text.encode("utf-8"))
    
    return Response(
        content=encoded_bytes, 
        media_type="text/plain",
        headers={"Cache-Control": "no-store"}
    )

@app.get("/my-sub-plain")
async def get_subscription_plain():
    """Версия без Base64 (в открытом виде)"""
    links = await get_all_links()
    if links is None:
        return Response(content="sources.txt not found", status_code=404)
        
    final_text = "\n".join(links)
    return Response(
        content=final_text, 
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "no-store"}
    )

if __name__ == "__main__":
    import uvicorn
    
    # Проверяем наличие сертификатов
    use_ssl = os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE)
    
    if use_ssl:
        print("[+] Запуск с поддержкой HTTPS")
        uvicorn.run(
            "main:app", 
            host="0.0.0.0", 
            port=8000, 
            ssl_keyfile=KEY_FILE, 
            ssl_certfile=CERT_FILE
        )
    else:
        print("[!] Сертификаты не найдены. Запуск по HTTP")
        uvicorn.run("main:app", host="0.0.0.0", port=8000)