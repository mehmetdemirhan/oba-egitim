"""Deploy referansı doğrulama (FAZ 2, madde 7).

Geliştiricinin girdiği "Git commit SHA / Vercel referansı"nı doğrular:
  1) Format kontrolü — SHA regex (7-40 hex) veya Vercel URL/deployment referansı
  2) Mümkünse GitHub API ile commit'in GERÇEKTEN var olduğunu teyit (GITHUB_REPO_OWNER/NAME/TOKEN)

Doğrulanamayan girişler BLOKLANMAZ — "doğrulanamadı" etiketiyle döner; admin şeffaf uyarıya rağmen
"biliyorum, devam et" diyebilir (deploy_kuyrugu.entegre-et bloklamaz, yalnız damgalar).
"""
import re

import httpx

from core.config import GITHUB_REPO_OWNER, GITHUB_REPO_NAME, GITHUB_TOKEN

_SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")
_VERCEL_RE = re.compile(r"(vercel\.app|vercel\.com|dpl_[A-Za-z0-9]+)", re.IGNORECASE)


async def dogrula(ref: str) -> dict:
    """ref → {gecerli: bool|None, yontem, tur, mesaj}.

    gecerli=True: teyit edildi; False: format geçersiz; None: format tamam ama teyit edilemedi
    (GitHub yapılandırılmadı/erişilemedi) → 'doğrulanamadı'."""
    ref = (ref or "").strip()
    if not ref:
        return {"gecerli": False, "yontem": "format", "tur": "bos", "mesaj": "Referans boş."}

    # Vercel referansı → yalnız format (Vercel API entegre değil, dürüstçe 'doğrulanamadı')
    if _VERCEL_RE.search(ref):
        return {"gecerli": None, "yontem": "format", "tur": "vercel",
                "mesaj": "Vercel referansı biçimsel olarak tanındı; canlı teyit yapılmadı (doğrulanamadı)."}

    m = _SHA_RE.match(ref)
    if not m:
        return {"gecerli": False, "yontem": "format", "tur": "bilinmiyor",
                "mesaj": "Girdi geçerli bir Git SHA (7-40 hex) veya Vercel referansına benzemiyor."}

    # Format OK → GitHub ile teyit dene
    if not (GITHUB_REPO_OWNER and GITHUB_REPO_NAME and GITHUB_TOKEN):
        return {"gecerli": None, "yontem": "format", "tur": "git_sha",
                "mesaj": "SHA biçimi geçerli; GitHub yapılandırılmadığı için commit varlığı teyit edilemedi (doğrulanamadı)."}
    try:
        url = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/commits/{ref}"
        headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
        async with httpx.AsyncClient(timeout=8.0) as ac:
            resp = await ac.get(url, headers=headers)
        if resp.status_code == 200:
            sha = resp.json().get("sha", ref)
            return {"gecerli": True, "yontem": "github", "tur": "git_sha",
                    "mesaj": f"Commit GitHub'da doğrulandı ({sha[:10]})."}
        if resp.status_code == 404:
            return {"gecerli": False, "yontem": "github", "tur": "git_sha",
                    "mesaj": "SHA biçimi geçerli ama commit repoda bulunamadı (404)."}
        return {"gecerli": None, "yontem": "github", "tur": "git_sha",
                "mesaj": f"GitHub teyidi yapılamadı (HTTP {resp.status_code}); doğrulanamadı."}
    except Exception as e:
        return {"gecerli": None, "yontem": "github", "tur": "git_sha",
                "mesaj": f"GitHub'a ulaşılamadı ({type(e).__name__}); SHA biçimi geçerli ama teyit edilemedi."}
