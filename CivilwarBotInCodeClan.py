import discord
from discord.ext import commands
import sqlite3
import os
import itertools

# 봇 설정: 토큰과 인텐트 설정
TOKEN = os.getenv('DISCORD_BOT_TOKEN')  # 환경 변수에서 Discord 봇 토큰 읽기
intents = discord.Intents.default()
intents.members = True            # 서버 멤버 관련 이벤트 허용
intents.voice_states = True       # 음성 상태 이벤트 허용
bot = commands.Bot(command_prefix='!', intents=intents)

# --- DB 조회 ---
def get_player_roles(nickname):
    """
    주어진 Discord 닉네임으로 SQLite DB(players.db)의 players 테이블에서
    discord_nick 컬럼을 조회하여 저장된 "포지션:점수" 문자열을 파싱 후
    {포지션: 스킬점수, ...} 형태의 dict 반환.
    존재하지 않으면 None 반환.
    """
    conn = sqlite3.connect('players.db')
    cursor = conn.cursor()
    cursor.execute(
        'SELECT role FROM players WHERE discord_nick = ?', (nickname,)
    )
    row = cursor.fetchone()
    conn.close()
    

    if not row:
        return None

    roles = {}
    # 예시 row[0]: "정글:92,미드:85"
    for part in row[0].split(','):
        pos, score = part.split(':')
        roles[pos.strip()] = int(score)
    return roles

# --- 인자 파싱 ---
def parse_fixed_args(args, guild):
    """
    명령어 인수 리스트(args)에서 '고정' 키워드를 찾아, 그 뒤에 오는
    "닉네임:포지션" 쌍을 [(Member, position), ...] 형식으로 변환.
    지원하지 않는 형식이나 포지션은 무시.
    """
    fixed = []
    if '고정' not in args:
        return fixed

    start = args.index('고정') + 1
    for token in args[start:]:
        try:
            nick, pos = token.split(':')
        except ValueError:
            break  # 형식 벗어나면 종료

        # 유효한 포지션인지 확인
        if pos not in ['탑', '정글', '미드', '원딜', '서폿']:
            continue

        # 서버 멤버 중 display_name과 일치하는 Member 객체 찾기
        member = discord.utils.find(
            lambda m: m.display_name == nick,
            guild.members
        )
        if member:
            fixed.append((member, pos))
    return fixed

# --- 멤버 필터링 ---
def split_members(members, exclude_requester, requester_id):
    """
    음성 채널 참여자 리스트에서 봇 계정 제거,
    '제외' 옵션이 활성화된 경우 요청자 ID도 제거.
    """
    filtered = [m for m in members if not m.bot]
    if exclude_requester:
        filtered = [m for m in filtered if m.id != requester_id]
    return filtered

# --- 팀 배치 로직 ---
POSITIONS = ['탑', '정글', '미드', '원딜', '서폿']

def find_best_assignment(players, fixed_slots=None):
    """
    전체 최적화(_best_full) 또는 고정 슬롯 포함 최적화(_best_with_fixed)를 호출.
    players: [{'member': Member, 'roles': {pos:score, ...}}, ...]
    fixed_slots: [(Member, pos), ...] 또는 None
    """
    if fixed_slots:
        return _best_with_fixed(players, fixed_slots)
    return _best_full(players)


def _best_full(players):
    """
    players 리스트를 정확히 절반으로 나누어(5명 대 5명),
    각 팀에 포지션 순열을 대입해 스킬 합이 최대인 조합을 찾고,
    두 팀의 스킬 합 차이가 최소인 배치 반환.
    """
    best = None
    # 5명 조합을 순회
    for team1 in itertools.combinations(players, 5):
        team2 = [p for p in players if p not in team1]
        s1, a1 = _assign_roles(team1, POSITIONS)
        s2, a2 = _assign_roles(team2, POSITIONS)
        if a1 and a2:
            diff = abs(s1 - s2)
            if best is None or diff < best[0]:
                best = (diff, a1, a2)
    return (best[1], best[2]) if best else (None, None)


def _best_with_fixed(players, fixed):
    """
    fixed 멤버 리스트를 양 팀에 번갈아 배치(fixed[::2] -> 팀1, fixed[1::2] -> 팀2),
    나머지 인원을 절반으로 나눠 스킬 격차 최소 배치 탐색.
    """
    best = None
    fixed1 = fixed[::2]
    fixed2 = fixed[1::2]
    # 나머지 후보
    rem = [p for p in players if p['member'] not in [f[0] for f in fixed]]
    half = (10 - len(fixed)) // 2

    for rem1 in itertools.combinations(rem, half):
        rem2 = [p for p in rem if p not in rem1]
        roles1 = [r for r in POSITIONS if r not in [f[1] for f in fixed1]]
        roles2 = [r for r in POSITIONS if r not in [f[1] for f in fixed2]]
        s1, a1 = _assign_roles_with_fixed(rem1, fixed1, roles1)
        s2, a2 = _assign_roles_with_fixed(rem2, fixed2, roles2)
        if a1 and a2:
            diff = abs(s1 - s2)
            if best is None or diff < best[0]:
                best = (diff, a1, a2)
    return (best[1], best[2]) if best else (None, None)


def _assign_roles(team, positions):
    """
    team 멤버 수와 동일한 길이의 positions 순열을 대입하여,
    유효(멤버가 해당 포지션 보유)한 배치만 고려,
    스킬 합이 최대인 배치와 그 합 반환.
    """
    best_sum = None
    best_assign = None
    for perm in itertools.permutations(positions, len(team)):
        total = 0
        assign = []
        valid = True
        for p, pos in zip(team, perm):
            if pos in p['roles']:
                total += p['roles'][pos]
                assign.append((p, pos))
            else:
                valid = False
                break
        if not valid:
            continue
        if best_sum is None or total > best_sum:
            best_sum = total
            best_assign = assign.copy()
    return best_sum, best_assign


def _assign_roles_with_fixed(rem, fixed, positions):
    """
    고정 멤버 목록(fixed)과 남은 rem 멤버 리스트에 대해,
    positions 순열 대입 후 유효한 배치만 고려,
    고정 멤버 점수 합 포함 전체 스킬 합과 배치 반환.
    """
    best_sum = None
    best_assign = None
    fixed_score = sum(p['roles'][pos] for p, pos in fixed)

    for perm in itertools.permutations(positions, len(rem)):
        total = fixed_score
        assign = fixed.copy()
        valid = True
        for p, pos in zip(rem, perm):
            if pos in p['roles']:
                total += p['roles'][pos]
                assign.append((p, pos))
            else:
                valid = False
                break
        if not valid:
            continue
        if best_sum is None or abs(total - fixed_score) > 0 and total > best_sum:
            best_sum = total
            best_assign = assign.copy()
    return best_sum, best_assign

# --- 결과 포맷 ---
def format_assignment(assign):
    """
    배치 리스트 [(Member, pos), ...]를 임베드 메시지용 문자열로 변환
    """
    return '\n'.join(
        f"{p['member'].display_name} (역할 {pos}, 스킬 {p['roles'][pos]})"
        for p, pos in assign
    )

# --- 커맨드 핸들러 ---
@bot.command(name='전적팀짜기')
async def assign_teams(ctx, *args):
    """
    사용자 명령어 처리:
    - '제외' 인자 처리: 호출자 제외 여부
    - '고정' 인자 처리:固定 멤버 파싱
    - 음성 채널 참여자 필터링, DB 조회
    - 최적화 함수 호출
    - 결과 임베드로 전송
    """
    exclude = '제외' in args
    fixed_slots = parse_fixed_args(args, ctx.guild)

    voice = ctx.author.voice
    if not voice or not voice.channel:
        return await ctx.send('음성 채널 참여 필요')

    members = split_members(voice.channel.members, exclude, ctx.author.id)
    if len(members) != 10:
        return await ctx.send(f'10명 필요 (현재 {len(members)})')

    players = []
    for m in members:
        roles = get_player_roles(m.display_name)
        if not roles:
            return await ctx.send(f"DB에 '{m.display_name}' 정보가 없습니다.")
        players.append({'member': m, 'roles': roles})

    team1, team2 = find_best_assignment(players, fixed_slots)
    if not team1:
        return await ctx.send('배치 실패')

    embed = discord.Embed(title='팀 배치 결과', color=0x00ff00)
    embed.add_field(name='팀 1', value=format_assignment(team1), inline=False)
    embed.add_field(name='팀 2', value=format_assignment(team2), inline=False)
    await ctx.send(embed=embed)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

if __name__ == '__main__':
    bot.run(TOKEN)
