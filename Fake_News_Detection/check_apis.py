"""API health check script — tests all 3 API integrations"""
import sys, requests
sys.path.insert(0, '.')
import config

SEP = '=' * 55

# ── 1. Google Fact Check API ─────────────────────────────────────
print(SEP)
print('[1] Google Fact Check API')
try:
    r = requests.get(
        'https://factchecktools.googleapis.com/v1alpha1/claims:search',
        params={
            'query': 'modi age 100 years',
            'key': config.GOOGLE_FACT_CHECK_API_KEY,
            'pageSize': 3
        },
        headers={'User-Agent': config.USER_AGENT},
        timeout=8
    )
    print(f'    HTTP Status : {r.status_code}')
    if r.status_code == 200:
        data = r.json()
        claims = data.get('claims', [])
        print(f'    Claims found: {len(claims)}')
        for c in claims[:2]:
            for rev in c.get('claimReview', [])[:1]:
                rating = rev.get('textualRating', 'N/A')
                pub    = rev.get('publisher', {}).get('name', 'N/A')
                print(f'      Rating: {rating} | Publisher: {pub}')
        print('    STATUS: OK')
    else:
        print(f'    STATUS: FAILED')
        print(f'    Response: {r.text[:200]}')
except Exception as e:
    print(f'    STATUS: ERROR - {e}')

# ── 2. NewsAPI ───────────────────────────────────────────────────
print()
print('[2] NewsAPI')
try:
    r = requests.get(
        'https://newsapi.org/v2/everything',
        params={
            'q': 'India cricket 2024',
            'pageSize': 3,
            'language': 'en',
            'apiKey': config.NEWS_API_KEY
        },
        headers={'User-Agent': config.USER_AGENT},
        timeout=8
    )
    print(f'    HTTP Status : {r.status_code}')
    if r.status_code == 200:
        data = r.json()
        articles = data.get('articles', [])
        print(f'    Articles found: {len(articles)}')
        for a in articles[:2]:
            src = a.get('source', {}).get('name', 'N/A')
            title = a.get('title', '')[:60]
            print(f'      [{src}] {title}')
        print('    STATUS: OK')
    else:
        print(f'    STATUS: FAILED')
        print(f'    Response: {r.text[:200]}')
except Exception as e:
    print(f'    STATUS: ERROR - {e}')

# ── 3. Wikipedia (always free) ───────────────────────────────────
print()
print('[3] Wikipedia API (always free)')
try:
    r = requests.get(
        'https://en.wikipedia.org/w/api.php',
        params={
            'action': 'query', 'prop': 'extracts',
            'exsentences': 2, 'exintro': True,
            'titles': 'Narendra Modi', 'format': 'json',
            'explaintext': True
        },
        headers={'User-Agent': config.USER_AGENT},
        timeout=8
    )
    print(f'    HTTP Status : {r.status_code}')
    if r.status_code == 200:
        pages = r.json()['query']['pages']
        extract = list(pages.values())[0].get('extract', '')
        print(f'    Extract (first 120 chars): {extract[:120]}')
        print('    STATUS: OK')
    else:
        print(f'    STATUS: FAILED - {r.status_code}')
except Exception as e:
    print(f'    STATUS: ERROR - {e}')

# ── 4. GDELT ─────────────────────────────────────────────────────
print()
print('[4] GDELT Real-Time News')
try:
    import urllib.parse, time
    time.sleep(6)  # GDELT rate limit
    q = urllib.parse.quote('India cricket 2024')
    r = requests.get(
        f'https://api.gdeltproject.org/api/v2/doc/doc?query={q}&mode=artlist&maxrecords=5&format=json',
        headers={'User-Agent': config.USER_AGENT},
        timeout=10
    )
    print(f'    HTTP Status : {r.status_code}')
    if r.status_code == 200 and r.text.strip():
        data = r.json()
        arts = data.get('articles', [])
        print(f'    Articles found: {len(arts)}')
        for a in arts[:2]:
            print(f'      {a.get("title", "")[:60]} | {a.get("domain", "")}')
        print('    STATUS: OK')
    elif r.status_code == 429:
        print('    STATUS: RATE LIMITED (try again in 5 sec)')
    else:
        print(f'    STATUS: NO RESULTS or error {r.status_code}')
except Exception as e:
    print(f'    STATUS: ERROR - {e}')

print()
print(SEP)
print('HEALTH CHECK COMPLETE')
print(SEP)
