"""Generate self-hosted GitHub stats cards (dark + light) for the profile README.

Runs in GitHub Actions with GITHUB_TOKEN. Writes:
  assets/{dark,light}/stats.svg     — headline numbers + top languages
  assets/{dark,light}/activity.svg  — contribution heatmap for the last year
"""
import base64, datetime as dt, json, os, pathlib, urllib.request

USER = os.environ.get('GH_USER', 'divyanshrajat')
ROOT = pathlib.Path(__file__).resolve().parents[2]
FONTS = pathlib.Path(__file__).parent / 'fonts'

THEMES = {
    'dark': dict(bg1='#0A0D13', bg2='#0F141E', card='#121826', stroke='#232C3F', text='#EEF1F6', soft='#C3CAD8',
                 muted='#8C95A8', a1='#3CF0B4', a2='#4CC9F0', amber='#FFB547', violet='#A594FF', dot='#1C2433',
                 scale=['#161C29', '#0F4A3C', '#16795E', '#25B588', '#3CF0B4']),
    'light': dict(bg1='#FFFFFF', bg2='#F5F7FA', card='#FFFFFF', stroke='#E1E6EE', text='#0B0F17', soft='#2E3747',
                  muted='#5E687A', a1='#0BA67A', a2='#1287B8', amber='#C27A00', violet='#6A55E0', dot='#E3E8EF',
                  scale=['#EDF1F5', '#B7EBD8', '#6FD3AF', '#22B383', '#0B8A63']),
}

QUERY = """
query($login:String!){ user(login:$login){
  followers{totalCount}
  repositories(ownerAffiliations:OWNER, first:100, privacy:PUBLIC, isFork:false){
    totalCount nodes{ stargazerCount languages(first:8, orderBy:{field:SIZE,direction:DESC}){ edges{ size node{name} } } } }
  contributionsCollection{ totalCommitContributions totalPullRequestContributions totalIssueContributions
    contributionCalendar{ totalContributions weeks{ contributionDays{ date contributionCount } } } }
}}"""


def fetch():
    req = urllib.request.Request('https://api.github.com/graphql',
                                 data=json.dumps({'query': QUERY, 'variables': {'login': USER}}).encode(),
                                 headers={'Authorization': f"bearer {os.environ['GITHUB_TOKEN']}", 'Content-Type': 'application/json'})
    data = json.load(urllib.request.urlopen(req))
    if 'errors' in data:
        raise SystemExit(data['errors'])
    return data['data']['user']


def summarise(u):
    cc = u['contributionsCollection']
    days = [d for w in cc['contributionCalendar']['weeks'] for d in w['contributionDays']]
    today = dt.date.today().isoformat()
    days = [d for d in days if d['date'] <= today]
    # streaks (today with 0 does not break the current streak yet)
    cur = 0
    for i, d in enumerate(reversed(days)):
        if d['contributionCount'] > 0:
            cur += 1
        elif i == 0:
            continue
        else:
            break
    best = run = 0
    for d in days:
        run = run + 1 if d['contributionCount'] > 0 else 0
        best = max(best, run)
    langs = {}
    for r in u['repositories']['nodes']:
        for e in r['languages']['edges']:
            langs[e['node']['name']] = langs.get(e['node']['name'], 0) + e['size']
    tot = sum(langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:6]
    return dict(total=cc['contributionCalendar']['totalContributions'], commits=cc['totalCommitContributions'],
                prs=cc['totalPullRequestContributions'], issues=cc['totalIssueContributions'],
                repos=u['repositories']['totalCount'], stars=sum(r['stargazerCount'] for r in u['repositories']['nodes']),
                followers=u['followers']['totalCount'], cur=cur, best=best,
                langs=[(n, s / tot) for n, s in top], weeks=cc['contributionCalendar']['weeks'])


def fontface():
    out = ''
    for fam, f in [('SG', 'sg700.woff2'), ('JBM', 'jbm400.woff2')]:
        out += "@font-face{font-family:'%s';src:url(data:font/woff2;base64,%s) format('woff2');}" % (
            fam, base64.b64encode((FONTS / f).read_bytes()).decode())
    return out


FF = None


def frame(T, w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<defs><style>{FF}</style>'
            f'<pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.3" fill="{T["dot"]}"/></pattern>'
            f'<linearGradient id="gx" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{T["a1"]}"/><stop offset="1" stop-color="{T["a2"]}"/></linearGradient>'
            f'<linearGradient id="bgf" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{T["bg2"]}"/><stop offset="1" stop-color="{T["bg1"]}"/></linearGradient></defs>'
            f'<rect width="{w}" height="{h}" rx="28" fill="url(#bgf)"/><rect width="{w}" height="{h}" rx="28" fill="url(#dots)"/>'
            f'<rect x=".75" y=".75" width="{w-1.5}" height="{h-1.5}" rx="28" fill="none" stroke="{T["stroke"]}" stroke-width="1.5"/>'
            + body + '</svg>')


def t(x, y, s, size, fill, fam='JBM', anchor='start', ls=0):
    s = str(s).replace('&', '&amp;').replace('<', '&lt;')
    return f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" letter-spacing="{ls}">{s}</text>'


def stats_svg(T, S):
    b = t(56, 64, 'git stats --live', 15, T['a1'])
    b += t(54, 112, 'Last 12 months on GitHub.', 40, T['text'], 'SG', ls=-1)
    b += t(1224, 112, f'updated {dt.date.today():%d %b %Y}', 14, T['muted'], anchor='end')
    tiles = [(f"{S['total']:,}", 'contributions', T['a1']), (f"{S['cur']}d", 'current streak', T['amber']),
             (f"{S['best']}d", 'longest streak', T['a2']), (f"{S['repos']}", 'public repos', T['violet'])]
    for i, (n, lab, c) in enumerate(tiles):
        x = 40 + i * 190
        b += f'<rect x="{x}" y="146" width="174" height="150" rx="20" fill="{T["card"]}" stroke="{T["stroke"]}" stroke-width="1.5"/>'
        b += f'<rect x="{x+22}" y="146" width="44" height="3" rx="1.5" fill="{c}"/>'
        b += t(x + 22, 222, n, 42, c, 'SG', ls=-1)
        b += t(x + 22, 256, lab, 14, T['muted'])
    sub = f"{S['commits']:,} commits · {S['prs']} PRs · {S['stars']} stars · {S['followers']} follower{'s' if S['followers'] != 1 else ''}"
    b += t(40, 336, sub, 14, T['muted'])
    # languages
    x0, y0, W = 820, 146, 420
    b += f'<rect x="{x0}" y="{y0}" width="{W}" height="200" rx="20" fill="{T["card"]}" stroke="{T["stroke"]}" stroke-width="1.5"/>'
    b += t(x0 + 24, y0 + 36, 'top languages', 14, T['muted'])
    cols = [T['a1'], T['a2'], T['amber'], T['violet'], T['muted'], T['soft']]
    bx = x0 + 24; bw = W - 48
    b += f'<clipPath id="lb"><rect x="{bx}" y="{y0+54}" width="{bw}" height="12" rx="6"/></clipPath><g clip-path="url(#lb)">'
    cx = bx
    for (n, p), c in zip(S['langs'], cols):
        b += f'<rect x="{cx:.1f}" y="{y0+54}" width="{bw*p+0.5:.1f}" height="12" fill="{c}"/>'
        cx += bw * p
    b += '</g>'
    for i, ((n, p), c) in enumerate(zip(S['langs'], cols)):
        lx = bx + (i % 2) * 190; ly = y0 + 100 + (i // 2) * 34
        b += f'<circle cx="{lx+6}" cy="{ly-5}" r="6" fill="{c}"/>'
        b += t(lx + 20, ly, n, 15, T['text'])
        b += t(lx + 172, ly, f'{p*100:.1f}%', 13, T['muted'], anchor='end')
    return frame(T, 1280, 370, b)


def activity_svg(T, S):
    weeks = S['weeks'][-53:]
    mx = max([d['contributionCount'] for w in weeks for d in w['contributionDays']] + [1])
    cell, gap = 17, 4
    x0, y0 = 88, 128
    b = t(56, 64, 'git log --graph', 15, T['a1'])
    b += t(54, 104, f"{S['total']:,} contributions in the last year", 30, T['text'], 'SG', ls=-.5)
    last_month = None
    for wi, w in enumerate(weeks):
        for d in w['contributionDays']:
            day = dt.date.fromisoformat(d['date'])
            c = d['contributionCount']
            lvl = 0 if c == 0 else min(4, 1 + int(3 * c / mx))
            x = x0 + wi * (cell + gap); y = y0 + 18 + day.isoweekday() % 7 * (cell + gap)
            b += f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="5" fill="{T["scale"][lvl]}"/>'
        m = dt.date.fromisoformat(w['contributionDays'][0]['date']).month
        if m != last_month:
            if last_month is not None and wi < 51:
                b += t(x0 + wi * (cell + gap), y0 + 6, dt.date(2000, m, 1).strftime('%b'), 13, T['muted'])
            last_month = m
    for i, lab in [(1, 'Mon'), (3, 'Wed'), (5, 'Fri')]:
        b += t(x0 - 12, y0 + 18 + i * (cell + gap) + 14, lab, 12, T['muted'], anchor='end')
    lx = 1224 - 5 * (cell + gap)
    b += t(lx - 10, 112, 'less', 12, T['muted'], anchor='end')
    for i in range(5):
        b += f'<rect x="{lx + i*(cell+gap)}" y="98" width="{cell}" height="{cell}" rx="5" fill="{T["scale"][i]}"/>'
    b += t(1232, 112, 'more', 12, T['muted'])
    return frame(T, 1280, 320, b)


def main():
    global FF
    FF = fontface()
    S = summarise(fetch())
    for name, T in THEMES.items():
        d = ROOT / 'assets' / name
        d.mkdir(parents=True, exist_ok=True)
        (d / 'stats.svg').write_text(stats_svg(T, S))
        (d / 'activity.svg').write_text(activity_svg(T, S))
    print(json.dumps({k: v for k, v in S.items() if k != 'weeks'}, default=str))


if __name__ == '__main__':
    main()
