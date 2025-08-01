#!/usr/bin/env python3
"""
FreeIPA entegrasyonu için MCP araçları.

Bu modül, FreeIPA dizin yönetim sistemleri ile etkileşim için Model Context Protocol (MCP) araçları sağlar.
Kullanıcıları ve grupları listeleme, gösterme, ekleme ve değiştirme işlevselliği içerir ve
MCP uyumlu arayüzler aracılığıyla FreeIPA verilerini yönetir.

Modül, ortam değişkenleri aracılığıyla kimlik doğrulama işlemlerini yönetir ve ağ ve kimlik doğrulama
sorunları için kapsamlı hata yönetimi sağlar.

Sağlanan Araçlar:
    - freeipa_connect: FreeIPA sunucusuna bağlan
    - freeipa_disconnect: FreeIPA sunucusundan bağlantıyı kes
    - freeipa_status: FreeIPA bağlantı durumunu kontrol et
    - user_list: Kullanıcıları listele
    - user_show: Kullanıcı detaylarını göster
    - user_add: Yeni kullanıcı ekle
    - user_modify: Kullanıcı detaylarını değiştir
    - group_list: Grupları listele
    - group_show: Grup detaylarını göster
    - group_add: Yeni grup ekle
    - group_add_member: Gruba kullanıcı ekle
    - group_remove_member: Gruptan kullanıcı çıkar

Gerekli Ortam Değişkenleri:
    - FREEIPA_SERVER: FreeIPA örneğinin temel URL'si veya host adı
    - FREEIPA_USERNAME: Kimlik doğrulama için kullanıcı adı
    - FREEIPA_PASSWORD: Kimlik doğrulama için şifre
    - FREEIPA_VERIFY_SSL: SSL doğrulaması ("true" veya "false", isteğe bağlı)

Bağımlılıklar:
    - python-freeipa: FreeIPA API etkileşimleri için Python kütüphanesi
    - python-dotenv: Ortam değişkeni yönetimi
    - fastmcp: FastMCP sunucu uygulaması
    - fastapi: Web framework
    - uvicorn: Uygulamayı çalıştırmak için ASGI sunucusu
    - starlette: ASGI toolkit
"""

import os
import sys
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import secrets
import string
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from starlette.routing import Mount
from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
try:
    from python_freeipa import ClientMeta
except ImportError:
    print("python-freeipa not installed. Install with: pip install python-freeipa", file=sys.stderr)
    sys.exit(1)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))

FREEIPA_SERVER = os.getenv("FREEIPA_SERVER")
FREEIPA_USERNAME = os.getenv("FREEIPA_USERNAME")
FREEIPA_PASSWORD = os.getenv("FREEIPA_PASSWORD")
FREEIPA_VERIFY_SSL = os.getenv("FREEIPA_VERIFY_SSL", "false").lower() == "true"

if not all([FREEIPA_SERVER, FREEIPA_USERNAME, FREEIPA_PASSWORD]):
    logger.error("FreeIPA connection parameters missing. Please set FREEIPA_SERVER, FREEIPA_USERNAME, FREEIPA_PASSWORD in .env file.")
    sys.exit(1)

# Global State
freeipa_client: Optional[ClientMeta] = None
freeipa_connected = False

# MCP Server
mcp = FastMCP("FreeIPA MCP Tools")

# Utility Functions
def safe_json_serialize(obj, max_depth=10, current_depth=0):
    if current_depth > max_depth:
        return "[Max Depth Exceeded]"
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    elif isinstance(obj, (list, tuple)):
        return [safe_json_serialize(item, max_depth, current_depth + 1) for item in obj]
    elif isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            try:
                result[str(key)] = safe_json_serialize(value, max_depth, current_depth + 1)
            except Exception as e:
                result[str(key)] = f"[Serialization Error: {str(e)}]"
        return result
    else:
        try:
            return str(obj)
        except Exception:
            return "[Unserializable Object]"

def connect_freeipa():
    """FreeIPA sunucusuna bağlan"""
    global freeipa_client, freeipa_connected
    
    try:
        freeipa_client = ClientMeta(FREEIPA_SERVER, verify_ssl=FREEIPA_VERIFY_SSL)
        freeipa_client.login(FREEIPA_USERNAME, FREEIPA_PASSWORD)
        freeipa_connected = True
        logger.info(f"FreeIPA sunucusuna başarıyla bağlandı: {FREEIPA_SERVER}")
        return True
        
    except Exception as e:
        logger.error(f"FreeIPA bağlantısı başarısız: {e}")
        freeipa_connected = False
        return False

def ensure_connection():
    """FreeIPA bağlantısını kontrol et ve gerekirse yeniden bağlan"""
    global freeipa_client, freeipa_connected
    
    if not freeipa_connected or not freeipa_client:
        return connect_freeipa()
    
    try:
        # Basit bir ping işlemi ile bağlantıyı test et
        freeipa_client.ping()
        return True
    except Exception as e:
        logger.warning(f"FreeIPA bağlantısı kayboldu, yeniden bağlanılıyor: {e}")
        return connect_freeipa()

# Tool Implementations
@mcp.tool()
async def freeipa_connect(server: str, username: str, password: str, verify_ssl: bool = True):
    """
    FreeIPA sunucusuna bağlan

    Args:
        server (str): FreeIPA sunucu adresi
        username (str): Kullanıcı adı
        password (str): Şifre
        verify_ssl (bool): SSL doğrulaması (varsayılan: True)
    
    Returns:
        dict: Bağlantı sonucu ve mesajı
    """
    global freeipa_client, freeipa_connected
    
    try:
        freeipa_client = ClientMeta(server, verify_ssl=verify_ssl)
        freeipa_client.login(username, password)
        freeipa_connected = True
        return {"result": f"FreeIPA sunucusuna başarıyla bağlandı: {server}"}
    except Exception as e:
        freeipa_connected = False
        return {"error": f"FreeIPA bağlantısı başarısız: {e}"}

@mcp.tool()
async def freeipa_disconnect():
    """
    FreeIPA bağlantısını kapat

    Returns:
        dict: Bağlantı kapatma sonucu ve mesajı
    """
    global freeipa_client, freeipa_connected
    
    try:
        if freeipa_client:
            freeipa_client.logout()
        freeipa_client = None
        freeipa_connected = False
        return {"result": "FreeIPA bağlantısı kapatıldı"}
    except Exception as e:
        return {"error": f"FreeIPA bağlantısı kapatılırken hata: {e}"}

@mcp.tool()
async def freeipa_status():
    """
    FreeIPA bağlantı durumunu kontrol et

    Returns:
        dict: Bağlantı durumu veya hata mesajı
    """
    global freeipa_connected
    
    if not freeipa_connected:
        return {"error": "FreeIPA sunucusuna bağlı değil"}
    
    try:
        if freeipa_client:
            result = freeipa_client.ping()
            return {"result": safe_json_serialize(result)}
    except Exception as e:
        freeipa_connected = False
        return {"error": f"FreeIPA bağlantısı kontrol edilirken hata: {e}"}

@mcp.tool()
async def change_password(username: str, new_password: str, old_password: str):
    """
    Kullanıcı şifresini biliyor fakat değiştirmek isterse şifresini resetle

    Args:
        uid (str): Kullanıcı adı
    
    Returns:
        dict: Resetlenen kullanıcı bilgisi veya hata mesajı
    """
    if not ensure_connection():
        return {"error": "FreeIPA sunucusuna bağlı değil"}
    
    try:
        res = freeipa_client.change_password(username=username, new_password=new_password, old_password=old_password)
        return {"result": safe_json_serialize(res.get("result", {}))}
    except Exception as e:
        return {"error": f"Kullanıcı detayları alınırken hata: {e}"}
    
@mcp.tool()
async def forgot_reset_password(username: str, phone: str, new_password: str = ""):
    """
    Kullanıcı şifresini unutmuşsa, telefon doğrulaması ile şifresini resetle ve yeni şifreyi belirlemesine izin ver.

    Args:
        username (str): Kullanıcı adı
        phone (str): Kullanıcının kayıtlı telefon numarası (doğrulama için)
        new_password (str): Kullanıcının belirlemek istediği yeni şifre (boşsa random şifre atanır)

    Returns:
        dict: Resetlenen kullanıcı bilgisi, yeni şifre veya hata mesajı
    """
    if not ensure_connection():
        return {"error": "FreeIPA sunucusuna bağlı değil"}

    def generate_password(length=12):
        import secrets, string
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def normalize_phone(phone):
        return phone.replace("+90", "").replace("0", "", 1).replace(" ", "").replace("-", "")

    try:
        user_info = freeipa_client.user_show(a_uid=username)
        ipa_phones = user_info.get("result", {}).get("telephonenumber", [])
        print(f"IPA phones: {ipa_phones}, input: {phone}")
        user_phones = [normalize_phone(p) for p in ipa_phones]
        input_phone = normalize_phone(phone)
        if not ipa_phones or input_phone not in user_phones:
            return {"error": "Telefon numarası doğrulanamadı veya sistemde kayıtlı değil."}

        temp_password = generate_password()
        res_mod = freeipa_client.user_mod(a_uid=username, o_userpassword=temp_password)

        if new_password:
            res_change = freeipa_client.change_password(
                username=username,
                new_password=new_password,
                old_password=temp_password
            )
            return {
                "result": "Şifre başarıyla sıfırlandı ve yeni şifre ayarlandı.",
                "username": username,
                "new_password": new_password
            }
        else:
            return {
                "result": "Şifre başarıyla sıfırlandı. Yeni şifre kullanıcıya iletildi.",
                "username": username,
                "new_password": temp_password
            }
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return {"error": f"Kullanıcı şifresi resetlenirken hata: {e}"}

@mcp.tool()
async def user_list(sizelimit: int = 100):
    """
    Kullanıcı listesini getir

    Args:
        sizelimit (int): Döndürülecek maksimum kullanıcı sayısı (varsayılan: 100)
    
    Returns:
        dict: Kullanıcı listesi veya hata mesajı
    """
    if not ensure_connection():
        return {"error": "FreeIPA sunucusuna bağlı değil"}
    
    try:
        res = freeipa_client.user_find(sizelimit=sizelimit)
        return {"result": safe_json_serialize(res.get("result", []))}
    except Exception as e:
        return {"error": f"Kullanıcı listesi alınırken hata: {e}"}

@mcp.tool()
async def user_show(uid: str):
    """
    Kullanıcı detaylarını getir

    Args:
        uid (str): Kullanıcı adı
    
    Returns:
        dict: Kullanıcı detayları veya hata mesajı
    """
    if not ensure_connection():
        return {"error": "FreeIPA sunucusuna bağlı değil"}
    
    try:
        res = freeipa_client.user_show(a_uid=uid)
        return {"result": safe_json_serialize(res.get("result", {}))}
    except Exception as e:
        return {"error": f"Kullanıcı detayları alınırken hata: {e}"}

@mcp.tool()
async def user_add(
    uid: str,
    givenname: str,
    sn: str,
    mail: str = "",
    userpassword: str = ""
):
    """
    Yeni kullanıcı ekle

    Args:
        uid (str): Kullanıcı adı
        givenname (str): Kullanıcının adı
        sn (str): Kullanıcının soyadı
        mail (str): Kullanıcının e-posta adresi (boş bırakılabilir)
        userpassword (str): Kullanıcı şifresi (boş bırakılabilir)
    
    Returns:
        dict: Eklenen kullanıcı bilgisi veya hata mesajı
    """
    if not ensure_connection():
        return {"error": "FreeIPA sunucusuna bağlı değil"}
    
    try:
        res = freeipa_client.user_add(
            a_uid=uid,
            a_givenname=givenname,
            a_sn=sn,
            o_mail=mail,
            o_userpassword=userpassword,
        )
        return {"result": safe_json_serialize(res.get("result", {}))}
    except Exception as e:
        return {"error": f"Kullanıcı eklenirken hata: {e}"}

@mcp.tool()
async def user_modify(uid: str, **kwargs):
    """
    Kullanıcı bilgilerini güncelle

    Args:
        uid (str): Kullanıcı adı
        kwargs: Güncellenecek alanlar (anahtar-değer)
    
    Returns:
        dict: Güncellenen kullanıcı bilgisi veya hata mesajı
    """
    if not ensure_connection():
        return {"error": "FreeIPA sunucusuna bağlı değil"}
    
    try:
        # Boş parametreleri filtrele
        params = {k: v for k, v in kwargs.items() if v is not None}
        res = freeipa_client.user_mod(a_uid=uid, **params)
        return {"result": safe_json_serialize(res.get("result", {}))}
    except Exception as e:
        return {"error": f"Kullanıcı güncellenirken hata: {e}"}

@mcp.tool()
async def group_list(sizelimit: int = 100, cn: str = "", description: str = ""):
    """
    Grup listesini getir

    Args:
        sizelimit (int): Döndürülecek maksimum grup sayısı (varsayılan: 100)
        cn (str): Grup adı için filtre (örn: 'f19*' ile başlayanlar)
        description (str): Grup açıklaması için filtre (örn: 'bbb*' vb)

    Returns:
        dict: Grup listesi veya hata mesajı
    """
    if not ensure_connection():
        return {"error": "FreeIPA sunucusuna bağlı değil"}
    try:
        if cn and description:
            res = freeipa_client.group_find(a_cn=cn, o_description=description, sizelimit=sizelimit)
        elif cn:
            res = freeipa_client.group_find(a_cn=cn, sizelimit=sizelimit)
        elif description:
            res = freeipa_client.group_find(o_description=description, sizelimit=sizelimit)
        else:
            res = freeipa_client.group_find(sizelimit=sizelimit)
        return {"result": safe_json_serialize(res.get("result", []))}
    except Exception as e:
        return {"error": f"Grup listesi alınırken hata: {e}"}

@mcp.tool()
async def group_show(cn: str):
    """
    Grup detaylarını getir

    Args:
        cn (str): Grup adı (common name)
    
    Returns:
        dict: Grup detayları veya hata mesajı
    """
    if not ensure_connection():
        return {"error": "FreeIPA sunucusuna bağlı değil"}
    
    try:
        res = freeipa_client.group_show(a_cn=cn)
        return {"result": safe_json_serialize(res.get("result", {}))}
    except Exception as e:
        return {"error": f'Grup detayları alınırken hata: {e}'}

@mcp.tool()
async def group_add(cn: str, description: str = ""):
    """
    Yeni grup ekle

    Args:
        cn (str): Grup adı (common name)
        description (str): Grup açıklaması (boş bırakılabilir)
    
    Returns:
        dict: Eklenen grup bilgisi veya hata mesajı
    """
    if not ensure_connection():
        return {"error": "FreeIPA sunucusuna bağlı değil"}
    
    try:
        res = freeipa_client.group_add(a_cn=cn, o_description=description)
        return {"result": safe_json_serialize(res.get("result", {}))}
    except Exception as e:
        return {"error": f"Grup eklenirken hata: {e}"}

@mcp.tool()
async def group_add_member(cn: str, user: str):
    """
    Gruba üye ekle

    Args:
        cn (str): Grup adı (common name)
        user (str): Kullanıcı adı
    
    Returns:
        dict: Güncellenen grup bilgisi veya hata mesajı
    """
    if not ensure_connection():
        return {"error": "FreeIPA sunucusuna bağlı değil"}
    
    try:
        res = freeipa_client.group_add_member(a_cn=cn, o_user=user)
        return {"result": safe_json_serialize(res.get("result", {}))}
    except Exception as e:
        return {"error": f"Gruba üye eklenirken hata: {e}"}

@mcp.tool()
async def group_remove_member(cn: str, user: str):
    """
    Gruptan üye çıkar

    Args:
        cn (str): Grup adı (common name)
        user (str): Kullanıcı adı
    
    Returns:
        dict: Güncellenen grup bilgisi veya hata mesajı
    """
    if not ensure_connection():
        return {"error": "FreeIPA sunucusuna bağlı değil"}
    
    try:
        res = freeipa_client.group_remove_member(a_cn=cn, o_user=user)
        return {"result": safe_json_serialize(res.get("result", {}))}
    except Exception as e:
        return {"error": f"Gruptan üye çıkarılırken hata: {e}"}

# SSE Transport
sse = SseServerTransport("/messages/")

app = FastAPI(docs_url=None, redoc_url=None)

from starlette.routing import Mount
app.router.routes.append(Mount("/messages", app=sse.handle_post_message))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["Health"])
async def health() -> dict:
    return {
        "status": "ok",
        "freeipa_connected": freeipa_connected,
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.4",
        "environment": {
            "server": FREEIPA_SERVER,
            "username": FREEIPA_USERNAME,
            "verify_ssl": FREEIPA_VERIFY_SSL
        }
    }

@app.get("/sse", tags=["MCP"])
async def handle_sse(request: Request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as (
        read_stream,
        write_stream,
    ):
        init_options = mcp._mcp_server.create_initialization_options()
        await mcp._mcp_server.run(
            read_stream,
            write_stream,
            init_options,
        )

@app.get("/connection-status", tags=["Health"])
async def connection_status() -> dict:
    return {
        "connected": freeipa_connected,
        "server": FREEIPA_SERVER,
        "timestamp": datetime.now().isoformat()
    }

@app.on_event("startup")
async def startup_event():
    connect_freeipa()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")

    uvicorn.run(app, host=host, port=port)