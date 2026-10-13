"""Responsive check for the AgentGate console: every view on 16 device sizes.

Needs Playwright with Chromium (pip install playwright && playwright install chromium).
Start the console first, then:

    python tools/responsive_check.py                       # checks http://127.0.0.1:8600/
    python tools/responsive_check.py http://127.0.0.1:8600/ screenshots/

Fails on: sideways page scroll, elements off-screen, clipped text, overlapping header items,
a misplaced nav marker, tap targets under 44px on touch screens, or the bottom of a page
hidden behind fixed bars. Exits non-zero when anything is found.
"""
import asyncio, json, sys
from playwright.async_api import async_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8600/"
OUT = sys.argv[2] if len(sys.argv) > 2 else None
DEVICES = [  # name, w, h, mobile/touch
    ("desktop-1440", 1440, 900, False), ("laptop-1280", 1280, 800, False),
    ("ipad-pro-land-1194", 1194, 834, True), ("ipad-air-land-1180", 1180, 820, True), ("ipad-land-1024", 1024, 768, True),
    ("ipad-pro-port-834", 834, 1194, True), ("ipad-air-port-820", 820, 1180, True), ("ipad-port-768", 768, 1024, True), ("ipad-mini-744", 744, 1133, True),
    ("iphone-promax-430", 430, 932, True), ("iphone-390", 390, 844, True), ("iphone-se-375", 375, 667, True), ("android-360", 360, 780, True), ("small-320", 320, 568, True),
    ("phone-land-844", 844, 390, True), ("phone-land-667", 667, 375, True),
]
VIEWS = ["switchboard", "activity", "gateway", "evidence", "agent"]

CHECK = r"""() => {
  const vw = document.documentElement.clientWidth, vh = window.innerHeight, issues = [];
  if (document.documentElement.scrollWidth > vw + 1) issues.push(`page scrolls sideways: ${document.documentElement.scrollWidth} > ${vw}`);
  const scrollers = el => { for (let p = el.parentElement; p; p = p.parentElement) { const o = getComputedStyle(p).overflowX; if (o === 'auto' || o === 'scroll') return true; } return false; };
  const visible = el => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el); return r.width > 1 && r.height > 1 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
  const view = document.querySelector('.view:not([hidden])');
  for (const el of [...document.querySelectorAll('.topbar *'), ...view.querySelectorAll('*')]) {
    if (!visible(el) || el.closest('svg') || el.closest('.nl')) continue;
    const r = el.getBoundingClientRect();
    if ((r.right > vw + 1 || r.left < -1) && !scrollers(el)) issues.push(`off-screen: ${el.tagName.toLowerCase()}.${el.className} ${Math.round(r.left)}..${Math.round(r.right)}`);
    const cs = getComputedStyle(el);
    if (el.children.length === 0 && el.textContent.trim() && el.scrollWidth > el.clientWidth + 1 && cs.overflowX !== 'auto' && cs.overflowX !== 'scroll' && cs.display !== 'inline' && !['TD','TH','TEXTAREA','INPUT'].includes(el.tagName))
      issues.push(`clipped text: ${el.tagName.toLowerCase()}.${el.className} "${el.textContent.trim().slice(0,30)}" ${el.scrollWidth}>${el.clientWidth}`);
  }
  // nav marker on the active item
  const ind = document.querySelector('.nav-ind'), a = document.querySelector('.nav a[aria-current=page]');
  if (ind && a) { const r = ind.getBoundingClientRect(), q = a.getBoundingClientRect();
    if (Math.abs(r.left - q.left) > 1.5 || Math.abs(r.top - q.top) > 1.5 || Math.abs(r.width - q.width) > 1.5) issues.push('nav marker misaligned'); }
  // every nav item reachable and tappable
  for (const n of document.querySelectorAll('.nav a')) { const r = n.getBoundingClientRect(); if (r.bottom > vh + 1 || r.right > vw + 1) issues.push('nav item outside viewport: ' + n.dataset.view);
    if (matchMedia('(pointer: coarse)').matches && r.height < 44) issues.push(`small tap target: nav ${n.dataset.view} ${Math.round(r.height)}px`); }
  if (matchMedia('(pointer: coarse)').matches) for (const b of view.querySelectorAll('.btn')) { const r = b.getBoundingClientRect(); if (r.height && r.height < 40) issues.push(`small tap target: ${b.textContent.trim()} ${Math.round(r.height)}px`); }
  // fixed bottom bar must not cover the last content once scrolled to the end
  const nav = document.querySelector('.nav');
  if (getComputedStyle(nav).position === 'fixed') {
    window.scrollTo(0, document.documentElement.scrollHeight);
    const last = [...view.querySelectorAll('.panel, .board, .figures')].filter(visible).pop();
    if (last && last.getBoundingClientRect().bottom > nav.getBoundingClientRect().top + 1) issues.push('bottom bar covers content');
    window.scrollTo(0, 0);
  }
  // nothing in the top bar / rail may overlap its neighbours
  const kids = [...document.querySelectorAll('.brand, .nav, .env, .mode, .lamps, .head > *, .board-top > *, .field-foot > *')].filter(visible);
  for (let i = 0; i < kids.length; i++) for (let j = i + 1; j < kids.length; j++) {
    const a = kids[i].getBoundingClientRect(), b = kids[j].getBoundingClientRect();
    if (kids[i].contains(kids[j]) || kids[j].contains(kids[i])) continue;
    if (a.left < b.right - 1 && b.left < a.right - 1 && a.top < b.bottom - 1 && b.top < a.bottom - 1)
      issues.push(`overlap: ${kids[i].className.baseVal ?? kids[i].className} × ${kids[j].className.baseVal ?? kids[j].className}`);
  }
  const flow = document.querySelector('#flow');
  return { issues, layout: flow.dataset.layout, flowW: Math.round(flow.getBoundingClientRect().width), rail: getComputedStyle(document.querySelector('.shell')).gridTemplateColumns };
}"""

async def main():
    report, failures = {}, 0
    async with async_playwright() as p:
        b = await p.chromium.launch()
        for name, w, h, mobile in DEVICES:
            ctx = await b.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if mobile else 1, is_mobile=mobile, has_touch=mobile)
            pg = await ctx.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "ERR_NAME_NOT_RESOLVED" not in m.text and "fonts" not in m.text else None)
            await pg.goto(BASE)
            await pg.wait_for_timeout(900)
            await pg.request.post(BASE + "api/clear", data="{}", headers={"Content-Type": "application/json"})
            dev = {}
            # exercise the main flows through the UI
            await pg.click("#btn-demo"); await pg.wait_for_timeout(3600)
            await pg.click("[data-s=Confidential]"); await pg.click("#btn-route"); await pg.wait_for_timeout(1800)
            for v in VIEWS:
                await pg.click(f".nav a[data-view={v}]"); await pg.wait_for_timeout(500)
                if v == "gateway":
                    await pg.click("[data-p='Customer record']"); await pg.click("#toolform button[type=submit]"); await pg.wait_for_timeout(1300)
                    await pg.click("[data-act=approve]"); await pg.wait_for_timeout(300); await pg.click("[data-act=execute]"); await pg.wait_for_timeout(600)
                if v == "evidence":
                    await pg.click("#case-filter [data-f=PRIVATE]"); await pg.wait_for_timeout(200)
                res = await pg.evaluate(CHECK)
                dev[v] = res
                failures += len(res["issues"])
                if OUT and name in ("desktop-1440", "ipad-port-768", "ipad-land-1024", "iphone-390", "small-320", "phone-land-844"):
                    await pg.screenshot(path=f"{OUT}/dev-{name}-{v}.png", full_page=(v != "agent"))
            dev["errors"] = errs
            failures += len(errs)
            report[name] = dev
            await ctx.close()
        await b.close()
    for name, dev in report.items():
        sw = dev["switchboard"]
        print(f"{name:20s} rail={sw['rail'][:14]:14s} flow={sw['layout']}@{sw['flowW']}px  issues=" +
              str(sum(len(dev[v]['issues']) for v in VIEWS)) + (f" errors={dev['errors']}" if dev['errors'] else ""))
        for v in VIEWS:
            for i in dev[v]["issues"][:6]:
                print(f"    [{v}] {i}")
    print("TOTAL ISSUES:", failures)
    return failures

if __name__ == "__main__":
    sys.exit(1 if asyncio.run(main()) else 0)
