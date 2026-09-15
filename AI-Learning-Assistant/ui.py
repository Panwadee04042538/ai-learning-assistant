import discord

from controllers.planning_controller import start_planning
from controllers.monitoring_controller import start_monitoring
from controllers.evaluation_controller import start_evaluation

# -----------------------------
# เลือกหัวข้อ
# -----------------------------

class TopicSelect(discord.ui.Select):

    def __init__(self, module_name):

        self.module_name = module_name

        options = [

            discord.SelectOption(
                label="Algorithm",
                value="algorithm",
                emoji="🧠"
            ),

            discord.SelectOption(
                label="Flowchart",
                value="flowchart",
                emoji="📈"
            ),

            discord.SelectOption(
                label="Pseudocode",
                value="pseudocode",
                emoji="💻"
            ),

        ]

        super().__init__(
            placeholder="เลือกบทเรียน",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):

        topic = self.values[0]

        # --------------------------
        # Planning
        # --------------------------

        if self.module_name.lower() == "planning":

            await interaction.response.defer()

            await start_planning(
                bot=interaction.client,
                ctx=interaction,
                topic=topic,
            )

            return

        # --------------------------
        # Monitoring
        # --------------------------

        elif self.module_name.lower() == "monitoring":

            await interaction.response.defer()

            await start_monitoring(
                bot=interaction.client,
                ctx=interaction,
                topic=topic,
            )

            return

        # --------------------------
        # Evaluation
        # --------------------------

        elif self.module_name.lower() == "evaluation":

            await interaction.response.defer()

            await start_evaluation(
        bot=interaction.client,
        ctx=interaction,
        topic=topic
    )

            return
    
        await interaction.response.send_message(
            f"✅ คุณเลือก\n"
            f"Module : **{self.module_name}**\n"
            f"Topic : **{topic}**",
            ephemeral=True
        )


# -----------------------------
# View เลือกหัวข้อ
# -----------------------------

class TopicView(discord.ui.View):

    def __init__(self, module_name):

        super().__init__(timeout=180)

        self.add_item(
            TopicSelect(module_name)
        )


# -----------------------------
# ปุ่ม Planning
# -----------------------------

class MainMenu(discord.ui.View):

    def __init__(self):

        super().__init__(timeout=300)

    @discord.ui.button(
        label="Planning",
        emoji="🧠",
        style=discord.ButtonStyle.primary
    )
    async def planning(

        self,

        interaction: discord.Interaction,

        button: discord.ui.Button

    ):

        await interaction.response.send_message(

            "📚 เลือกบทเรียน",

            view=TopicView("Planning"),

            ephemeral=True

        )

    @discord.ui.button(
        label="Monitoring",
        emoji="🔍",
        style=discord.ButtonStyle.success
    )
    async def monitoring(

        self,

        interaction: discord.Interaction,

        button: discord.ui.Button

    ):

        await interaction.response.send_message(

            "📚 เลือกบทเรียน",

            view=TopicView("Monitoring"),

            ephemeral=True

        )

    @discord.ui.button(
        label="Evaluation",
        emoji="📊",
        style=discord.ButtonStyle.secondary
    )
    async def evaluation(

        self,

        interaction: discord.Interaction,

        button: discord.ui.Button

    ):

        await interaction.response.send_message(

            "📚 เลือกบทเรียน",

            view=TopicView("Evaluation"),

            ephemeral=True

        )
