import discord
from discord.ext import commands
import requests
<<<<<<< HEAD
from collections import defaultdict
=======
>>>>>>> d7c31a3c870aeb3b972fccd42e316f76cb826e6b


intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

headers = {
    "Authorization": f"Bearer {PUBG_API_KEY}",
    "Accept": "application/vnd.api+json"
}

@bot.event
async def on_ready():
    print(f'✅ 봇 로그인 완료: {bot.user}')

@bot.command(name="전적")
async def show_stats(ctx, nickname: str):
    """
    사용자가 !전적 <닉네임> 명령어를 입력했을 때 호출됩니다.
    PUBG API를 통해 플레이어 정보를 조회하고, 최근 매치 팀원들의 딜량을 Embed 메시지로 전송합니다.
    """
    # 1) 플레이어 검색: PUBG API의 players 엔드포인트를 호출하여 플레이어 ID와 매치 목록을 조회합니다.
    try:
        url = f"https://api.pubg.com/shards/steam/players?filter[playerNames]={nickname}"  # steam 서버로 변경
        response = requests.get(url, headers=headers)
    except requests.RequestException:
        await ctx.send("⚠️ PUBG API 요청 중 오류가 발생했습니다.")
        return

    # API 호출 결과 확인
    if response.status_code == 404:
        await ctx.send(f"⚠️ `{nickname}` 의 플레이어 정보를 찾을 수 없습니다. 닉네임을 확인해 주세요.")
        return
    elif response.status_code != 200:
        await ctx.send(f"⚠️ 플레이어 정보를 가져오는 중 오류가 발생했습니다 (HTTP {response.status_code}).")
        return

    player_data = response.json()

    # 검색된 플레이어가 없거나 오류일 경우 처리
    if "data" not in player_data or not player_data["data"]:
        await ctx.send(f"🔍 플레이어 `{nickname}` 를 찾을 수 없습니다.")
        return

    # 플레이어의 PUBG 계정 ID 가져오기
    player_id = player_data["data"][0]["id"]
    # 플레이어 정보에서 최근 매치 목록 추출
    matches = player_data["data"][0]["relationships"]["matches"]["data"]
    if not matches:
        await ctx.send(f"🔍 플레이어 `{nickname}` 의 최근 매치 기록이 없습니다.")
        return

    # 최신 매치 ID 선택 (리스트의 첫 번째 항목이라고 가정)
    latest_match_id = matches[0]["id"]

    # 2) 매치 정보 요청: 선택된 매치의 상세 정보를 조회합니다.
    try:
        match_url = f"https://api.pubg.com/shards/steam/matches/{latest_match_id}"  # steam 서버로 변경
        match_response = requests.get(match_url, headers=headers)
    except requests.RequestException:
        await ctx.send("⚠️ 매치 정보를 가져오는 중 오류가 발생했습니다.")
        return

    if match_response.status_code != 200:
        await ctx.send(f"⚠️ 매치 정보를 가져오는 중 오류 (HTTP {match_response.status_code}).")
        return

    match_data = match_response.json()

    included = match_data.get("included", [])

    # 3) 참가자 정보 파싱: 매치 데이터의 included 항목에서 참가자 목록을 추출합니다.
    participants = [i for i in included if i["type"] == "participant"]
    rosters = [i for i in included if i["type"] == "roster"]

    # 해당 플레이어의 participant ID 찾기
    player_participant = None
    for part in participants:
        if part["attributes"]["stats"].get("name") == nickname:
            player_participant = part
            break

    if not player_participant:
        await ctx.send(f"⚠️ `{nickname}` 의 participant 정보를 찾을 수 없습니다.")
        return

    player_participant_id = player_participant["id"]

    # 이 participant가 속한 roster 찾기
    player_roster = None
    for roster in rosters:
        roster_participants = [p["id"] for p in roster["relationships"]["participants"]["data"]]
        if player_participant_id in roster_participants:
            player_roster = roster
            break

    if not player_roster:
        await ctx.send(f"⚠️ `{nickname}` 의 팀(roster) 정보를 찾을 수 없습니다.")
        return

    # 해당 roster의 모든 팀원 participant ID
    teammate_ids = [p["id"] for p in player_roster["relationships"]["participants"]["data"]]
    teammates = [p for p in participants if p["id"] in teammate_ids]

    # 팀원들의 딜량 정보를 저장하는 리스트
    team_stats = []
    for mate in teammates:
        stats = mate["attributes"]["stats"]
        name = stats.get("name", "Unknown")
        damage = stats.get("damageDealt", 0)
        team_stats.append((name, damage))

    # 딜량을 기준으로 내림차순 정렬
    team_stats.sort(key=lambda x: x[1], reverse=True)

    # 4) Discord Embed 메시지 생성: 팀원별 딜량 정보를 보기 좋게 구성합니다.
    embed = discord.Embed(
        title=f"{nickname}님의 최근 경기 팀원 딜량",
        description=f"매치 ID: {latest_match_id}",
        color=discord.Color.blue()
    )

    for name, damage in team_stats:
        embed.add_field(name=name, value=f"딜량: {damage}", inline=False)

    embed.set_footer(text="PUBG 팀 전적 조회 봇")
    await ctx.send(embed=embed)
<<<<<<< HEAD

@bot.command(name="10판평균딜량")
async def show_average_damage(ctx, nickname: str):
    """
    사용자가 !10판평균딜량 <닉네임> 명령어를 입력했을 때 호출됩니다.
    PUBG API를 통해 최근 10판의 매치에 대한 팀원들의 평균 딜량을 조회하여 출력합니다.
    """
    try:
        url = f"https://api.pubg.com/shards/steam/players?filter[playerNames]={nickname}"
        response = requests.get(url, headers=headers)
    except requests.RequestException:
        await ctx.send("⚠️ PUBG API 요청 중 오류가 발생했습니다.")
        return

    if response.status_code == 404:
        await ctx.send(f"⚠️ `{nickname}` 의 플레이어 정보를 찾을 수 없습니다. 닉네임을 확인해 주세요.")
        return
    elif response.status_code != 200:
        await ctx.send(f"⚠️ 플레이어 정보를 가져오는 중 오류가 발생했습니다 (HTTP {response.status_code}).")
        return

    player_data = response.json()

    if "data" not in player_data or not player_data["data"]:
        await ctx.send(f"🔍 플레이어 `{nickname}` 를 찾을 수 없습니다.")
        return

    player_id = player_data["data"][0]["id"]
    matches = player_data["data"][0]["relationships"]["matches"]["data"]
    if len(matches) < 10:
        await ctx.send(f"🔍 `{nickname}` 의 최근 매치 기록이 10판 미만입니다.")
        return

    last_10_match_ids = [match["id"] for match in matches[:10]]

    all_team_stats = defaultdict(list)  # 각 팀원의 딜량을 저장
    teammate_play_count = defaultdict(int)  # 각 팀원과 함께 플레이한 횟수를 저장

    for match_id in last_10_match_ids:
        try:
            match_url = f"https://api.pubg.com/shards/steam/matches/{match_id}"
            match_response = requests.get(match_url, headers=headers)
        except requests.RequestException:
            await ctx.send(f"⚠️ 매치 {match_id} 정보를 가져오는 중 오류가 발생했습니다.")
            continue

        if match_response.status_code != 200:
            await ctx.send(f"⚠️ 매치 {match_id} 정보를 가져오는 중 오류 (HTTP {match_response.status_code}).")
            continue

        match_data = match_response.json()
        included = match_data.get("included", [])

        participants = [i for i in included if i["type"] == "participant"]
        rosters = [i for i in included if i["type"] == "roster"]

        player_participant = None
        for part in participants:
            if part["attributes"]["stats"].get("name") == nickname:
                player_participant = part
                break

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

        # 해당 매치에서 nickname과 함께 플레이한 팀원들
        teammate_names = [mate["attributes"]["stats"].get("name", "Unknown") for mate in teammates]

        # nickname과 함께 플레이한 팀원들의 딜량 기록
        for mate in teammates:
            stats = mate["attributes"]["stats"]
            name = stats.get("name", "Unknown")
            damage = stats.get("damageDealt", 0)
            all_team_stats[name].append(damage)

            # nickname과 함께 플레이한 팀원들의 플레이 횟수를 카운트
            if nickname in teammate_names and name != nickname:
                teammate_play_count[(nickname, name)] += 1
                teammate_play_count[(name, nickname)] += 1

    # 팀원별 평균 딜량 계산
    team_average_damage = []
    for name, damages in all_team_stats.items():
        average_damage = sum(damages) / len(damages)
        team_average_damage.append((name, average_damage))

    # 딜량을 기준으로 내림차순 정렬
    team_average_damage.sort(key=lambda x: x[1], reverse=True)

    embed = discord.Embed(
        title=f"{nickname}님의 최근 10판 팀원 평균 딜량 및 플레이 횟수",
        color=discord.Color.blue()
    )

    for name, avg_damage in team_average_damage:
        # 각 팀원과의 플레이 횟수도 표시
        play_count = teammate_play_count.get((nickname, name), 0)
        embed.add_field(name=name, value=f"평균 딜량: {avg_damage:.2f} / 함께 플레이한 횟수: {play_count}", inline=False)

    embed.set_footer(text="PUBG 팀 전적 조회 봇")
    await ctx.send(embed=embed)


=======
>>>>>>> d7c31a3c870aeb3b972fccd42e316f76cb826e6b
# ==== 봇 실행 ====
bot.run(DISCORD_TOKEN)