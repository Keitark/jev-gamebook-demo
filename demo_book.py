"""An original, redistributable navigation-only story. Not Lone Wolf text."""
from gamebook_jev import Choice, ProjectAonBook, Section

TITLE = "The Ashen Gate"
OBJECTIVE = "Reach the city through the Ashen Gate before the last light fades."
# id: (caption, narrative paragraphs, choices, terminal failure)
PASSAGES = {
    "1": (
        "Where the road divides",
        ["Beyond the ruined milestone, the forest road divides. To the east, a weathered bridge crosses black water. To the north, a narrow trail climbs towards a watchtower, its windows holding the last of the light.",
         "Your letter must reach the city before nightfall. Cut into the milestone are six small words: ‘Trust the road the river remembers.’"],
        [("7", "Cross the old bridge and follow the river."), ("3", "Climb the trail to the watchtower."), ("5", "Leave the road and enter the woods.")], False),
    "7": (
        "The ferryman's warning",
        ["The bridge bends beneath your feet but holds. On the far bank, a ferryman sits beside an empty boat. He turns a copper coin between his fingers without looking up.",
         "‘The eastern arch is sound,’ he says. ‘The western one is only a reflection. Remember that when you hear the bell.’ A towpath continues beneath the willows; stone steps lead down to his boat."],
        [("9", "Take the towpath beneath the willows."), ("4", "Ask the ferryman to carry you downstream.")], False),
    "3": (
        "A light in the tower",
        ["The watchtower door hangs open. Inside, an old keeper is winding a clock with no hands. Across his table lies a map, its river drawn in blue ink and its roads all scratched away.",
         "He traces the river to a pair of arches. ‘East for the living. West for those who have forgotten.’ From the parapet you can see a stair descending to the water."],
        [("9", "Descend the stair to the riverside gate."), ("1", "Return to the milestone and reconsider.")], False),
    "5": (
        "Under the black boughs",
        ["The forest closes behind you. Pale flowers line a deer track, and something beyond the trees whistles a tune you almost remember. To your right, through the roots, you hear running water.",
         "A scrap of a traveller's coat hangs from a branch. The track continues deeper into the wood. The water, at least, still knows where it is going."],
        [("7", "Follow the sound of the river."), ("6", "Follow the whistling deeper into the trees.")], False),
    "4": (
        "The boat without an oar",
        ["The ferryman smiles, but does not rise. ‘This boat makes only one journey,’ he says. The rope at its prow is tied to nothing at all.",
         "You step back. Upstream, the towpath is still visible in the dusk. Downstream, the water seems to run uphill into a bank of mist."],
        [("9", "Leave the boat and take the towpath."), ("6", "Untie the rope and enter the mist.")], False),
    "9": (
        "Two arches at twilight",
        ["At the foot of the city wall stand two identical arches. A bell sounds once. Beneath the western arch the moon shines in a sky that has not yet grown dark. Beneath the eastern arch, a lantern swings in the wind.",
         "No sign names either entrance. The river divides around the stonework, and for a moment even the sound of water falls silent. What did the stranger tell you?"],
        [("8", "Step beneath the eastern arch."), ("6", "Enter the western arch."), ("7", "Return upstream to ask the ferryman.")], False),
    "8": (
        "The lantern keeper",
        ["The lantern keeper is a child in a coat much too large for her. She sees the seal on your letter and steps aside. Beyond her, stairs climb to a door of ash-grey oak.",
         "‘One last choice,’ she says. ‘Knock, and they will hear you. Ring the bell, and something else will.’ The brass knocker is warm beneath your hand."],
        [("12", "Use the brass knocker and deliver the letter."), ("6", "Pull the bell rope instead.")], False),
    "6": (
        "The road that forgets",
        ["The light disappears. When you look behind you, the path has vanished too. Somewhere very far away, a bell rings a second time.",
         "Your journey ends here. The letter will not reach the city tonight."], [], True),
    "12": (
        "Before the last light",
        ["The door opens on a courtyard filled with the scent of bread. A woman takes your letter, checks the seal, and lets out a breath she seems to have been holding for years.",
         "Behind you the lantern is extinguished. Ahead, the city is waking. You have found the Ashen Gate, and you have arrived in time."], [], False),
}


def make_demo() -> ProjectAonBook:
    return ProjectAonBook({
        sid: Section(id=sid, text="\n\n".join(paragraphs),
                     choices=[Choice(f"c{i}", target, label) for i, (target, label) in enumerate(choices)],
                     deadend=dead, paragraphs=paragraphs, title=title)
        for sid, (title, paragraphs, choices, dead) in PASSAGES.items()
    })
