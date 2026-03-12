import base64
import asyncio
import binascii
import httpx
from fastapi import FastAPI, Response

app = FastAPI()

SOURCES_FILE = "/app/data/sources.txt"

HEADERS = {"User-Agent": "v2rayN/6.31"} 

def decode_base64(text: str) -> str:
    text = text.strip()
    text += "=" * ((4 - len(text) % 4) % 4)
    try:
        return base64.b64decode(text).decode('utf-8', errors='ignore')
    except (binascii.Error, ValueError):
        return text

async def fetch_subscription(client: httpx.AsyncClient, url: str) -> list[str]:
    links = []
    try:
        resp = await client.get(url, timeout=10.0)
        resp.raise_for_status()
        
        text = resp.text
        if "://" not in text:
            text = decode_base64(text)
            
        for sub_line in text.splitlines():
            sub_line = sub_line.strip()
            if sub_line and not sub_line.startswith(("http://", "https://")):
                links.append(sub_line)
    except Exception as e:
        print(f"[!] Ошибка при скачивании {url}: {e}")
    
    return links

@app.get("/my-secret-sub")
async def get_subscription():
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
        return Response(content="sources.txt not found", status_code=404)

    async with httpx.AsyncClient(verify=False, headers=HEADERS) as client:
        tasks = [fetch_subscription(client, url) for url in http_urls]
        results = await asyncio.gather(*tasks)
        
        for sub_links in results:
            combined_links.extend(sub_links)
    
    unique_links = list(dict.fromkeys(combined_links))
    
    final_text = "\n".join(unique_links)
    encoded_bytes = base64.b64encode(final_text.encode("utf-8"))
    
    return Response(
        content=encoded_bytes, 
        media_type="text/plain",
        headers={"Cache-Control": "no-store"}
    )