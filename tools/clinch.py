#!/usr/bin/env python3
"""Who has clinched a playoff spot, and who has been eliminated.

Six of fourteen teams make the bracket. Seeding is record first, then points
for -- no division override. The regular season is weeks 1-14.

A team has CLINCHED when there is no arrangement of the remaining games that
leaves six other teams above it. A team is ELIMINATED when there is no
arrangement that puts it in the top six.

Run it after the archive has been updated for the week:

    python3 tools/clinch.py                      # conservative, no schedule
    python3 tools/clinch.py --sched week8_14.json   # exact

Without a schedule the answer is sound but can lag the true clinch by a week:
it assumes any rival can win out, when in fact rivals play each other and
cannot all do so. With the remaining schedule it is exact. The schedule file
is a JSON list of [week, teamA, teamB] using the manager names in the
archive, e.g.  [[8,"Bill","Owen"],[8,"Jon","Michael"], ...]

Points-for tiebreaks are unknowable in advance, so every tie is resolved
AGAINST the team being tested. That keeps the script from ever announcing a
clinch that has not actually happened, which is the only error that matters
when the answer goes in the newsletter.
"""
import argparse, itertools, json, os, sys

SPOTS = 6
LAST_REGULAR_WEEK = 14
HERE = os.path.dirname(os.path.abspath(__file__))
ARCHIVE = os.path.join(HERE, '..', 'public', 'archive.json')


def standings(archive, season=None, through=None):
    d = json.load(open(archive))
    M, TW = d['mgrs'], d['tw']
    season = season or max(r[0] for r in TW)
    played = [r for r in TW if r[0] == season and r[1] <= LAST_REGULAR_WEEK]
    through = through or max(r[1] for r in played)
    rec, pf = {}, {}
    for r in played:
        if r[1] > through:
            continue
        m = M[r[3]]
        rec[m] = rec.get(m, 0) + (1 if r[5] == 1 else 0)
        pf[m] = pf.get(m, 0.0) + r[6]
    return season, through, rec, pf


def maxflow(cap, s, t, n):
    """Dinic, small graphs."""
    from collections import deque
    flow = 0
    while True:
        lvl = [-1] * n
        lvl[s] = 0
        q = deque([s])
        while q:
            u = q.popleft()
            for v in range(n):
                if lvl[v] < 0 and cap[u][v] > 0:
                    lvl[v] = lvl[u] + 1
                    q.append(v)
        if lvl[t] < 0:
            return flow
        it = [0] * n

        def dfs(u, f):
            if u == t:
                return f
            while it[u] < n:
                v = it[u]
                if cap[u][v] > 0 and lvl[v] == lvl[u] + 1:
                    d = dfs(v, min(f, cap[u][v]))
                    if d:
                        cap[u][v] -= d
                        cap[v][u] += d
                        return d
                it[u] += 1
            return 0

        while True:
            f = dfs(s, 10 ** 9)
            if not f:
                break
            flow += f


def can_all_reach(need, games, teams):
    """Can every team in `need` reach its win target, given `games` left?

    Each remaining game hands exactly one win to one of its two teams. A game
    involving a team outside the set is still usable -- that team can lose it.
    """
    need = {k: v for k, v in need.items() if v > 0}
    if not need:
        return True
    usable = [g for g in games if g[0] in need or g[1] in need]
    total = sum(need.values())
    if total > len(usable):
        return False
    idx = {t: i for i, t in enumerate(need)}
    nG, nT = len(usable), len(need)
    n = 1 + nG + nT + 1
    S, T = 0, n - 1
    cap = [[0] * n for _ in range(n)]
    for gi, (a, b) in enumerate(usable):
        cap[S][1 + gi] = 1
        for side in (a, b):
            if side in idx:
                cap[1 + gi][1 + nG + idx[side]] = 1
    for t, k in need.items():
        cap[1 + nG + idx[t]][T] = k
    return maxflow(cap, S, T, n) == total


def analyse(rec, pf, left, games=None):
    teams = sorted(rec, key=lambda m: (-rec[m], -pf[m]))
    out = {}
    for t in teams:
        floor = rec[t]                      # t loses every remaining game
        ceil = rec[t] + left
        # --- clinched? can SPOTS rivals all finish at or above t's floor? ---
        rivals = [o for o in teams if o != t and rec[o] + left >= floor]
        if len(rivals) < SPOTS:
            clinched = True
        elif games is None:
            clinched = False                # conservative
        else:
            # t loses out, so t's own games are wins for its opponents
            rest = [g for g in games if t not in g]
            bonus = {}
            for a, b in games:
                if a == t:
                    bonus[b] = bonus.get(b, 0) + 1
                elif b == t:
                    bonus[a] = bonus.get(a, 0) + 1
            clinched = True
            for S in itertools.combinations(rivals, SPOTS):
                need = {o: floor - rec[o] - bonus.get(o, 0) for o in S}
                if any(rec[o] + left < floor for o in S):
                    continue
                if can_all_reach(need, rest, teams):
                    clinched = False
                    break
        # --- eliminated? can t reach the top six at all? ---
        better = [o for o in teams if o != t and rec[o] > ceil]
        eliminated = len(better) >= SPOTS
        out[t] = dict(rec=rec[t], pf=pf[t], floor=floor, ceil=ceil,
                      clinched=clinched, eliminated=eliminated,
                      rivals=len(rivals))
    return teams, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--archive', default=ARCHIVE)
    ap.add_argument('--sched', help='JSON [[week, teamA, teamB], ...] of games not yet played')
    ap.add_argument('--through', type=int)
    ap.add_argument('--season', type=int, help='defaults to the latest season in the archive')
    a = ap.parse_args()
    season, through, rec, pf = standings(a.archive, season=a.season, through=a.through)
    left = LAST_REGULAR_WEEK - through
    games = None
    if a.sched:
        games = [(g[1], g[2]) for g in json.load(open(a.sched)) if g[0] > through]
    print('%d, through week %d -- %d game%s left, %d of %d make the bracket'
          % (season, through, left, '' if left == 1 else 's', SPOTS, len(rec)))
    print('mode: %s\n' % ('exact (schedule supplied)' if games else
                          'conservative (no schedule -- a clinch may show a week late)'))
    teams, out = analyse(rec, pf, left, games)
    clinched, eliminated = [], []
    for i, t in enumerate(teams, 1):
        o = out[t]
        tag = 'CLINCHED' if o['clinched'] else ('ELIMINATED' if o['eliminated'] else '')
        print('  %2d. %-9s %2d-%-2d %8.2f   %2d-%-2d to %2d-%-2d   %s'
              % (i, t, o['rec'], through - o['rec'], o['pf'],
                 o['floor'], LAST_REGULAR_WEEK - o['floor'],
                 o['ceil'], LAST_REGULAR_WEEK - o['ceil'], tag))
        if o['clinched']:
            clinched.append(t)
        if o['eliminated']:
            eliminated.append(t)
    print()
    print('clinched this far:  ' + (', '.join(clinched) if clinched else 'nobody'))
    print('eliminated:         ' + (', '.join(eliminated) if eliminated else 'nobody'))
    if clinched:
        print('\n--> Each clinching team gets a segment in this week\'s issue,')
        print('    so a CLINCHED graphic can be made for them.')


if __name__ == '__main__':
    main()
