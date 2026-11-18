### Entry 1 11/17 20:00
I instructed Claude Code to create a minimal working game that I could inspect
and build further upon. This is the prompt I used:
```
Build the first playable version of the game. It should only contain a game screen, a player,
a floor or platform, left/right movement, jumping, keyboard input, and a goal.
Make it as small as possible.
```
The product I recieved from this prompt worked perfectly. No major issues and it will
allow me to build the project out further.

Testing of this stage included playing the game for a minute to ensure functionality.
---
### Entry 2 11/17 20:50
I used Claude Code to further build out the the gravity and collision handing. Interestingly,
it had already built them out in the previous stage, so this stage mainly involved verification
that the systems worked properly. Prompt:
```
Verify that the following mechanics are working: gravity, jumping, landing, horizontal movement,
collision detection, falling, boundaries
```
Looking at the source code and manually testing the game all show these systems in place.
---
### Entry 3 11/17 21:15
In this stage I continued building out the levels, using a text based JSON design. Prompt:
```
Make a couple more levels and store them in separate files. The second one should have gaps.
elevated platforms, hazards, and a more difficult route to the goal. The third should have more
than one hazard, more complicated arrangements of platforms, a final goal, and should be the
hardest. The levels should allow the user to move to the next level without restarting the program.
Hazards (spikes in this case) should be noted as "x" in the level files. Move level 1 to the level
files as well.
```
Claude Code generated three levels which I then played through and verified that all components
worked properly.
One thing that I wanted to change was the lack of any visual feedback on death, besides a simple
reset back to the beginning of the level. I requested a change to this with a prompt:
```
Add feedback on death. An animation where nom's mouth opens and both edges turn until they meet
each other and a small delay will do.
```
The animation was added with no issues.

### Entry 4 11/17 21:45
I began to add more advanced aspects of the game.
```
Add advanced aspects of gameplay. Include a GUI with current level, score (pellets),
lives (3, with a "you loose" screen), and instructions (accessible by hitting ? key)
```
This prompt gave me these mechanics. Testing demonstrated no problems.

---
### Entry 5 11/18 10:48
I wanted to make it so jump did not have a fixed height. This would make collection of
some pellets easier. Prompt:
```
Make it so jump height is contingent upon how long space is pressed.
```
The change was simple so it did not create any issues when added.
I also wanted to make the codebase easier to read to an onlooker, so I prompted Claude
Code with the following:
```
Utilize the principle of conditional inversion to make the codebase more readable.
```

### Bug 1
The character continues moving when touching the world edge
Fix: Record previous position, and if the world edge clamp moved the character back,
then set x velocity to zero
```
new_x = self.x + self.vx * DT
self.x = max(0.0, min(self.x, self.cols * TITLE - SIZE))
if self.x != new_x:
    self.vx = 0.0
```

### Bug 2
The previous fix created a new bug, the character does not move at all.
The fix was a simple typo, instead of claming the old position the new one should be.
```
self.x = max(0.0, min(new_x, self.cols * TITLE - SIZE))
```

### Bug 3
Keys get stuck on "held" when window focus changes.
Fixed this by adding a listener in the main JavaScript file.
```
addEventListener("blur", () => keys.clear());
```
