from enum import Enum
from functools import partial
from typing import Callable, NamedTuple, TypeAlias

from discord import ButtonStyle, Embed, Guild, Interaction, Member
from draftphase.bot import DISCORD_BOT
from draftphase.db import get_cursor
from draftphase.discord_utils import CallableButton, View

EMOJIS = [
    "🥇",
    "🥈",
    "🥉",
]

class UserPrediction(NamedTuple):
    user_id: int
    num_guessed: int
    num_correct_winner: int
    num_correct_score: int

class UserPredictionScore(NamedTuple):
    name: str
    score: int
    total: int
    rate: float

ScoreFn: TypeAlias = Callable[[UserPrediction], int]

class LeaderboardTypeDetails(NamedTuple):
    name: str
    description: str
    score_fn: ScoreFn
    total_fn: ScoreFn

class LeaderboardType(Enum):
    WINNER = LeaderboardTypeDetails(
        "Correct winner",
        "Sorted by times correctly predicted winner of a match",
        lambda x: x.num_correct_winner,
        lambda x: x.num_guessed,
    )
    SCORE = LeaderboardTypeDetails(
        "Correct score",
        "Sorted by times correctly predicted final score of a match",
        lambda x: x.num_correct_score,
        lambda x: x.num_guessed,
    )
    COMGINED = LeaderboardTypeDetails(
        "Combined",
        "Sorted by times correctly predicted winner of a match.\nDouble points for correct predictions of the final score.",
        lambda x: x.num_correct_winner + x.num_correct_score,
        lambda x: 2 * x.num_guessed,
    )

def get_user_predictions() -> list[UserPrediction]:
    with get_cursor() as cur:
        cur.execute(
            "SELECT"
            " user_id,"
            " COUNT(id) AS num_guessed,"
            " COUNT(CASE WHEN (predictions.team1_score > 2) = (games.team1_score > 2) THEN 1 END) AS num_correct_winner,"
            " COUNT(CASE WHEN (predictions.team1_score = games.team1_score) THEN 1 END) AS num_correct_score"
            " FROM predictions"
            " INNER JOIN games ON predictions.game_id = games.channel_id"
            " WHERE games.team1_score IS NOT NULL"
            " GROUP BY user_id"
        )
        return [UserPrediction(*row) for row in cur.fetchall()]

def get_score(prediction: UserPrediction, score_fn: ScoreFn, guild: Guild) -> UserPredictionScore:
    score = score_fn(prediction)
    rate = (score / prediction.num_guessed)

    user = guild.get_member(prediction.user_id)
    if not user:
        user = DISCORD_BOT.get_user(prediction.user_id)

    username = user.display_name if user else "Unknown user"
    return UserPredictionScore(username, score, prediction.num_guessed, rate)

class PredictionLeaderboardView(View):
    def __init__(self, member: Member):
        super().__init__(timeout=600)
        self.predictions = get_user_predictions()
        self.leaderboard_type = LeaderboardType.WINNER
        self.member = member

        self.buttons = {
            lb_type: CallableButton(
                partial(self.set_leaderboard_type, lb_type),
                label=lb_type.value.name,
                style=ButtonStyle.blurple,
            )
            for lb_type in LeaderboardType
        }

        for button in self.buttons.values():
            self.add_item(button)
        
    async def set_leaderboard_type(self, lb_type: LeaderboardType, interaction: Interaction):
        self.leaderboard_type = lb_type
        embed = self.get_embed_update_self()
        await interaction.response.edit_message(embed=embed, view=self)

    def get_embed_update_self(self):
        embed = Embed()
        score_fn = self.leaderboard_type.value.score_fn
        self.predictions.sort(key=lambda x: score_fn(x) * 1000 - x.num_guessed, reverse=True)

        # Display top 3
        for i in range(min(3, len(self.predictions))):
            score = get_score(self.predictions[i], score_fn, self.member.guild)

            embed.add_field(
                name=f"{EMOJIS[i]} {score.name}",
                value=f"**{score.score}** / {score.total} (**{score.rate:.1%}**)",
                inline=True,
            )

        line = "`{rank: <6}{username: <20}{score: <6}{total: <6}{rate: <6}`"
        lines = [
            "**" + line.format(rank="RANK", username="USERNAME", score="RIGHT", total="TOTAL", rate="RATE") + "**"
        ]

        # Display top 20
        for i in range(min(20, len(self.predictions))):
            score = get_score(self.predictions[i], score_fn, self.member.guild)
            lines.append(line.format(
                rank="#" + str(i + 1),
                username=score.name,
                score=score.score,
                total=score.total,
                rate="{:.1%}".format(score.rate),
            ))
        
        # Find index of self.member in self.predictions
        for i, prediction in enumerate(self.predictions):
            if (prediction.user_id == self.member.id):
                break
        else:
            i += 1
            prediction = UserPrediction(self.member.id, 0, 0, 0)
        
        # Display score of self.member if not in top 20
        if (i > 20):
            score = get_score(prediction, score_fn, self.member.guild)

            lines.append("...")
            lines.append(line.format(
                rank="#" + str(i + 1),
                username=score.name,
                score=score.score,
                total=score.total,
                rate=score.rate,
            ))

        embed.add_field(
            name="All scores",
            value="\n".join(lines),
            inline=False,
        )

        # Disable/enable buttons
        for lb_type, button in self.buttons.items():
            button.disabled = (lb_type == self.leaderboard_type)

        embed.set_footer(text=self.leaderboard_type.value.description)
        return embed

