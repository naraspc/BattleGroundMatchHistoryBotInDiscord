import discord
from discord.ext import commands
import requests
from collections import defaultdict
import re



intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

headers = {
    "Authorization": f"Bearer {PUBG_API_KEY}",
    "Accept": "application/vnd.api+json"
}

# 디스코드 봇 로그인 성공 시 호출되는 이벤트
@bot.event
async def on_ready():
    print(f'✅ 봇 로그인 완료: {bot.user}')

# 플레이어 정보를 가져오는 함수
def get_player_data(nickname):
    url = f"https://api.pubg.com/shards/steam/players?filter[playerNames]={nickname}"
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None

# 매치 정보를 가져오는 함수
def get_match_data(match_id):
    match_url = f"https://api.pubg.com/shards/steam/matches/{match_id}"
    try:
        match_response = requests.get(match_url, headers=headers)
        match_response.raise_for_status()
        return match_response.json()
    except requests.RequestException:
        return None

# 플레이어의 참가자 정보 찾기
def find_player_participant(participants, nickname):
    for part in participants:
        if part["attributes"]["stats"].get("name") == nickname:
            return part
    return None

# 팀원들의 딜량 정보 추출
def extract_team_stats(rosters, participants, player_participant_id):
    player_roster = None
    for roster in rosters:
        roster_participants = [p["id"] for p in roster["relationships"]["participants"]["data"]]
        if player_participant_id in roster_participants:
            player_roster = roster
            break
    
    if not player_roster:
        return []

    teammate_ids = [p["id"] for p in player_roster["relationships"]["participants"]["data"]]
    teammates = [p for p in participants if p["id"] in teammate_ids]

    team_stats = []
    for mate in teammates:
        stats = mate["attributes"]["stats"]
        name = stats.get("name", "Unknown")
        damage = stats.get("damageDealt", 0)
        team_stats.append((name, damage))

    team_stats.sort(key=lambda x: x[1], reverse=True)
    return team_stats

# 전적을 출력하는 함수
async def show_match_stats(ctx, nickname, match_id):
    match_data = get_match_data(match_id)
    if not match_data:
        await ctx.send(f"⚠️ 매치 정보를 가져오는 중 오류가 발생했습니다.")
        return

    included = match_data.get("included", [])
    participants = [i for i in included if i["type"] == "participant"]
    rosters = [i for i in included if i["type"] == "roster"]

    player_participant = find_player_participant(participants, nickname)
    if not player_participant:
        await ctx.send(f"⚠️ `{nickname}` 의 participant 정보를 찾을 수 없습니다.")
        return

    player_participant_id = player_participant["id"]
    team_stats = extract_team_stats(rosters, participants, player_participant_id)

    embed = discord.Embed(
        title=f"{nickname}님의 최근 경기 팀원 딜량",
        description=f"매치 ID: {match_id}",
        color=discord.Color.blue()
    )

    for name, damage in team_stats:
        embed.add_field(name=name, value=f"딜량: {damage}", inline=False)

    embed.set_footer(text="PUBG 팀 전적 조회 봇")
    await ctx.send(embed=embed)

# 최근 매치 기록을 가져와 출력하는 함수
async def show_latest_match_stats(ctx, nickname):
    player_data = get_player_data(nickname)
    if not player_data or "data" not in player_data or not player_data["data"]:
        await ctx.send(f"🔍 플레이어 `{nickname}` 를 찾을 수 없습니다.")
        return

    player_id = player_data["data"][0]["id"]
    matches = player_data["data"][0]["relationships"]["matches"]["data"]
    if not matches:
        await ctx.send(f"🔍 플레이어 `{nickname}` 의 최근 매치 기록이 없습니다.")
        return

    latest_match_id = matches[0]["id"]
    await show_match_stats(ctx, nickname, latest_match_id)

# 10판 평균 딜량을 계산하는 함수
async def show_average_damage(ctx, nickname, match_count=10):
    player_data = get_player_data(nickname)
    if not player_data or "data" not in player_data or not player_data["data"]:
        await ctx.send(f"🔍 플레이어 `{nickname}` 를 찾을 수 없습니다.")
        return

    matches = player_data["data"][0]["relationships"]["matches"]["data"]
    if len(matches) < match_count:
        await ctx.send(f"🔍 `{nickname}` 의 최근 매치 기록이 {match_count}판 미만입니다.")
        return

    last_n_match_ids = [match["id"] for match in matches[:match_count]]

    all_team_stats = defaultdict(list)
    teammate_play_count = defaultdict(int)

    for match_id in last_n_match_ids:
        match_data = get_match_data(match_id)
        if not match_data:
            await ctx.send(f"⚠️ 매치 {match_id} 정보를 가져오는 중 오류가 발생했습니다.")
            continue

        included = match_data.get("included", [])
        participants = [i for i in included if i["type"] == "participant"]
        rosters = [i for i in included if i["type"] == "roster"]


        player_participant = find_player_participant(participants, nickname)
        if not player_participant:
            continue

        player_participant_id = player_participant["id"]
        player_roster = None
        for roster in rosters:
            roster_participants = [p["id"] for p in roster["relationships"]["participants"]["data"]]
            if player_participant_id in roster_participants:
                player_roster = roster
                break

        if not player_roster:
            continue

        teammate_ids = [p["id"] for p in player_roster["relationships"]["participants"]["data"]]
        teammates = [p for p in participants if p["id"] in teammate_ids]

        teammate_names = [mate["attributes"]["stats"].get("name", "Unknown") for mate in teammates]

        for mate in teammates:
            stats = mate["attributes"]["stats"]
            name = stats.get("name", "Unknown")
            damage = stats.get("damageDealt", 0)
            all_team_stats[name].append(damage)

            if nickname in teammate_names and name != nickname:
                teammate_play_count[(nickname, name)] += 1
                teammate_play_count[(name, nickname)] += 1

    team_average_damage = []
    for name, damages in all_team_stats.items():
        average_damage = sum(damages) / len(damages)
        team_average_damage.append((name, average_damage))

    team_average_damage.sort(key=lambda x: x[1], reverse=True)

    embed = discord.Embed(
        title=f"{nickname}님의 최근 {match_count}판 팀원 평균 딜량 및 플레이 횟수",
        color=discord.Color.blue()
    )

    for name, avg_damage in team_average_damage:
        play_count = teammate_play_count.get((nickname, name), 0)
        embed.add_field(name=name, value=f"평균 딜량: {avg_damage:.2f} / 함께 플레이한 횟수: {play_count}", inline=False)

    embed.set_footer(text="PUBG 팀 전적 조회 봇 Made By Code 미르")
    await ctx.send(embed=embed)

# 명령어: 10판평균딜량 (횟수도 입력받도록 수정)
@bot.command(name="전적많이조회")
async def show_avg_damage(ctx, nickname: str, match_count: int = 10):
    await show_average_damage(ctx, nickname, match_count)

# 봇 실행
bot.run(DISCORD_TOKEN)