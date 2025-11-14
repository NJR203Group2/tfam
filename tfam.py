from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import time

BASE = "https://www.tfam.museum"
INFO_URL = f"{BASE}/Common/editor.aspx?id=230&ddlLang=zh-tw"  # 參觀資訊頁
URL  = f"{BASE}/Exhibition/Exhibition.aspx?ddlLang=zh-tw"     # 展覽資訊頁

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
driver.get(URL)
driver.maximize_window()
main_handle = driver.current_window_handle

# ====== 抓取參觀資訊（以 find() + if/else） ======
driver.execute_script("window.open('about:blank','_blank');")
driver.switch_to.window(driver.window_handles[-1])
driver.get(INFO_URL)
WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

info_soup = BeautifulSoup(driver.page_source, "html.parser")

# 1) 地址 / 電話 / 傳真 / 電子郵件：都在 <ul class="unstyled spacingB-20"> 的 li 裡
addr_text = tel_text = fax_text = mail_text = ""

info_ul = info_soup.find("ul", {"class": "unstyled spacingB-20"})
if info_ul:
    # 地址
    li_addr = None
    for li in info_ul.find_all("li", recursive=False):
        if "地址" in li.get_text():
            li_addr = li
            break
    if li_addr:
        a = li_addr.find("a")
        if a and a.get_text(strip=True):
            addr_text = a.get_text(strip=True)
        else:
            t = li_addr.get_text(" ", strip=True)
            pos = t.find("：")
            addr_text = t[pos+1:].strip() if pos != -1 else t

    # 電話
    li_tel = None
    for li in info_ul.find_all("li", recursive=False):
        if "電話" in li.get_text():
            li_tel = li
            break
    if li_tel:
        t = li_tel.get_text(" ", strip=True)
        pos = t.find("：")
        tel_text = t[pos+1:].strip() if pos != -1 else t

    # 傳真
    li_fax = None
    for li in info_ul.find_all("li", recursive=False):
        if "傳真" in li.get_text():
            li_fax = li
            break
    if li_fax:
        t = li_fax.get_text(" ", strip=True)
        pos = t.find("：")
        fax_text = t[pos+1:].strip() if pos != -1 else t

    # 電子郵件
    li_mail = None
    for li in info_ul.find_all("li", recursive=False):
        if "電子郵件" in li.get_text():
            li_mail = li
            break
    if li_mail:
        a = li_mail.find("a", href=lambda h: h and h.startswith("mailto:"))
        if a and a.get_text(strip=True):
            mail_text = a.get_text(strip=True)
        else:
            t = li_mail.get_text(" ", strip=True)
            pos = t.find("：")
            mail_text = t[pos+1:].strip() if pos != -1 else t

# 2) 開放時間：在 <div class="spacingB-20 web"> 裡的 <table class="table1">
open_text = ""
open_wrap = info_soup.find("div", {"class": "spacingB-20 web"})
if open_wrap:
    tbl = open_wrap.find("table", {"class": "table1"})
    if tbl:
        tds = [td.get_text(strip=True) for td in tbl.select("tbody tr td")]
        weekdays = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
        parts = []
        for i, day in enumerate(weekdays):
            val = tds[i] if i < len(tds) else ""
            parts.append(f"{day}：{val or '-'}")
        open_text = " / ".join(parts)

driver.close()
driver.switch_to.window(main_handle)

# ====== 捲動到底，讓清單載滿 ======
last_h = driver.execute_script("return document.body.scrollHeight")
for _ in range(15):
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(1.0)
    new_h = driver.execute_script("return document.body.scrollHeight")
    if new_h == last_h:
        break
    last_h = new_h

# 清單頁 HTML
list_soup = BeautifulSoup(driver.page_source, "html.parser")
cards = driver.find_elements(By.CSS_SELECTOR, "a.ExPage")

rows = []
seen = set()

# ====== 清單頁抓展覽資訊 ======
for el in cards:
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        title_fallback = (el.get_attribute("title") or el.text or "").strip()

        # 清單頁抓地點
        place_text = ""
        try:
            match = None
            for block in list_soup.select("div.row.Exhibition_list"):
                if title_fallback in str(block):
                    match = block
                    break
            if match:
                place_el = match.find("p", {"class": "info-middle"})
                place_text = place_el.get_text(strip=True) if place_el else ""
        except Exception:
            place_text = ""

        # 進入詳情頁（這版仍假設開新分頁）
        before = set(driver.window_handles)
        el.click()
        WebDriverWait(driver, 6).until(lambda d: len(set(d.window_handles) - before) > 0)
        new_tab = list(set(driver.window_handles) - before)[0]
        driver.switch_to.window(new_tab)

        WebDriverWait(driver, 8).until(
            EC.any_of(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.exhibition-title")),
                EC.presence_of_element_located((By.CSS_SELECTOR, "h1")),
                EC.presence_of_element_located((By.CSS_SELECTOR, "p.date-middle"))
            )
        )

        url = driver.current_url
        if "/Exhibition/" not in url or "id=" not in url or url in seen:
            driver.close()
            driver.switch_to.window(main_handle)
            continue
        seen.add(url)

        soup = BeautifulSoup(driver.page_source, "html.parser")

        # 展覽名稱
        name_el = soup.find("span", {"id": "CPContent_lbExName"}) or soup.find("h1")
        name_text = name_el.get_text(strip=True) if name_el else title_fallback

        # 日期
        date_el = soup.find("span", {"id": "CPContent_lbDate"})
        date_text = date_el.get_text(strip=True) if date_el else ""

        # 介紹
        intro_el = soup.find("div", {"class": "info-content txt"})
        intro_text = intro_el.get_text(strip=True) if intro_el else ""

        rows.append({
            "展覽名稱": name_text,
            "連結": url,
            "地點": place_text,
            "日期": date_text,
            "介紹": intro_text
        })

        driver.close()
        driver.switch_to.window(main_handle)

    except Exception:
        try:
            driver.switch_to.window(main_handle)
        except Exception:
            pass
        continue

driver.quit()

# ====== 匯出 ======
df_exhibitions = pd.DataFrame(
    rows,
    columns=["展覽名稱", "連結", "地點", "日期", "介紹"]
)

df_info = pd.DataFrame([{
    "展覽名稱": "",
    "連結": "",
    "地點": "",
    "日期": "",
    "介紹": "",
    "地址": addr_text,
    "電話": tel_text,
    "傳真": fax_text,
    "電子郵件": mail_text,
    "開放時間": open_text
}])


with open("tfam_exhibitions.csv", "w", encoding="utf-8-sig") as f:
    df_exhibitions.to_csv(f, index=False)
    f.write("\n\n")  # 插入兩行，代表新段落
    df_info.to_csv(f, index=False)

df_all = pd.concat([df_exhibitions, df_info], ignore_index=True)

df_all.to_csv("tfam_exhibitions.csv", index=False, encoding="utf-8-sig")

print(f"已輸出 tfam_exhibitions.csv")