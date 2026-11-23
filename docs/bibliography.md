# UX/UI bibliography

Sources behind the PrismaFlow audit (Deliver phase) and the `local/gemma3-4b-ux` fine-tune.
The training data in `training/` does not copy any of these texts. It is made of rules I wrote myself from them and of worked examples computed by the app's own audit. The **Rule used** line under each source says how PrismaFlow applies it.

Citations were checked against publisher pages, DOIs and author pages in November 2026.

## Pointing, choice and task time

1. **Fitts, P. M. (1954).** The information capacity of the human motor system in controlling the amplitude of movement. *Journal of Experimental Psychology, 47*(6), 381–391. https://doi.org/10.1037/h0055392
   Rule used: movement time grows with the index of difficulty ID = log2(2D/W). PrismaFlow computes ID from the target width (S/M/L = 24/40/56 px) and the thumb distance (bottom/center/top = 120/320/560 px). It flags ID > 4.5.

2. **MacKenzie, I. S. (1992).** Fitts' law as a research and design tool in human-computer interaction. *Human–Computer Interaction, 7*(1), 91–139. https://doi.org/10.1207/s15327051hci0701_3. Open copy: https://www.yorku.ca/mack/HCI1992.pdf
   Rule used: the linear form MT = a + b·ID, with a = 0.1 s and b = 0.15 s/bit in the app. MacKenzie also argues that the target size is what designers should change first.

3. **Bi, X., Li, Y., & Zhai, S. (2013).** FFitts law: Modeling finger touch with Fitts' law. In *Proc. CHI 2013* (pp. 1363–1372). ACM. https://doi.org/10.1145/2470654.2466180. Open copy: https://research.google/pubs/ffitts-law-modeling-finger-touch-with-fitts-law/
   Rule used: on touch screens the finger adds its own endpoint spread, so targets well below ~7–10 mm are much harder to hit than classic Fitts predicts. This is why PrismaFlow treats S (24 px) as a minor-link size only.

4. **Hick, W. E. (1952).** On the rate of gain of information. *Quarterly Journal of Experimental Psychology, 4*(1), 11–26. https://doi.org/10.1080/17470215208416600

5. **Hyman, R. (1953).** Stimulus information as a determinant of reaction time. *Journal of Experimental Psychology, 45*(3), 188–196. https://doi.org/10.1037/h0056940
   Rule used (4–5): decision time RT = a + b·log2(n + 1), with a = 0.25 s and b = 0.15 s in the app. A screen with more than 7 visible choices is flagged, and the fix is to keep about 5 and group the rest behind "Więcej".

6. **Card, S. K., Moran, T. P., & Newell, A. (1980).** The keystroke-level model for user performance time with interactive systems. *Communications of the ACM, 23*(7), 396–410. https://doi.org/10.1145/358886.358895

7. **Card, S. K., Moran, T. P., & Newell, A. (1983).** *The Psychology of Human-Computer Interaction.* Lawrence Erlbaum Associates. ISBN 978-0-89859-243-6.
   Rule used (6–7): time to goal is a sum of operators. Each screen step costs M = 1.35 s of mental preparation, plus the Hick time of the screen, plus the Fitts time of the tapped control.

## Mobile ergonomics and touch targets

8. **Wobbrock, J. O., Myers, B. A., & Aung, H. H. (2008).** The performance of hand postures in front- and back-of-device interaction for mobile computing. *International Journal of Human-Computer Studies, 66*(12), 857–875. https://doi.org/10.1016/j.ijhcs.2008.03.004. Open copy: https://faculty.washington.edu/wobbrock/pubs/ijhcs-08.pdf
   Rule used: one-handed thumb use is slower and less precise than index-finger use, so frequent actions belong where the thumb rests.

9. **Hoober, S. (2013, February 18).** How do users really hold mobile devices? *UXmatters.* https://www.uxmatters.com/mt/archives/2013/02/how-do-users-really-hold-mobile-devices.php
   Rule used: about half of observed phone use was one-handed, and the thumb drives most taps. Primary actions go in the bottom "thumb zone". The top corners are the hardest to reach.

10. **W3C (2023).** *Web Content Accessibility Guidelines (WCAG) 2.2.* W3C Recommendation, 5 October 2023. https://www.w3.org/TR/WCAG22/
    - SC 2.5.8 Target Size (Minimum), Level AA: at least 24 × 24 CSS px, unless one of the exceptions applies (spacing, an equivalent control, inline, user agent, essential). https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum
    - SC 2.5.5 Target Size (Enhanced), Level AAA: at least 44 × 44 CSS px. https://www.w3.org/WAI/WCAG22/Understanding/target-size-enhanced
    Rule used: PrismaFlow reports AA (≥ 24 px) and AAA (≥ 44 px) coverage. It counts a navigating control below 44 px as an issue and fixes it with a resize to L.

11. **Google.** *Material Design 3: Accessibility — designing for touch targets* (48 × 48 dp minimum). https://m3.material.io/foundations/designing/structure ; Android accessibility help: https://support.google.com/accessibility/android/answer/7101858

12. **Apple.** *Human Interface Guidelines: Accessibility* (hit targets of at least 44 × 44 pt). https://developer.apple.com/design/human-interface-guidelines/accessibility
    Rule used (11–12): the platform guidelines agree with WCAG AAA. A primary button is L (56 px) and is never smaller than M (40 px).

## Heuristics and cognition

13. **Nielsen, J. (1994, updated 2020/2024).** 10 usability heuristics for user interface design. *Nielsen Norman Group.* https://www.nngroup.com/articles/ten-usability-heuristics/
    Also: Nielsen, J., & Molich, R. (1990). Heuristic evaluation of user interfaces. *Proc. CHI '90*, 249–256. https://doi.org/10.1145/97243.97281
    Rule used: user control and freedom (no dead ends), recognition rather than recall, aesthetic and minimalist design (fewer visible options).

14. **Norman, D. A. (2013).** *The Design of Everyday Things* (revised and expanded ed.). Basic Books. ISBN 978-0-465-05065-9.
    Rule used: affordances, signifiers and feedback. Every control has a short verb label, and every non-goal screen shows a clear next step.

15. **Krug, S. (2014).** *Don't Make Me Think, Revisited: A Common Sense Approach to Web Usability* (3rd ed.). New Riders. ISBN 978-0-321-96551-6.
    Rule used: cut words and choices, and make the obvious path the big one.

16. **Miller, G. A. (1956).** The magical number seven, plus or minus two: Some limits on our capacity for processing information. *Psychological Review, 63*(2), 81–97. https://doi.org/10.1037/h0043158

17. **Sweller, J. (1988).** Cognitive load during problem solving: Effects on learning. *Cognitive Science, 12*(2), 257–285. https://doi.org/10.1207/s15516709cog1202_4
    Rule used (16–17): keep working memory load low. Show at most about 7 choices at once and remove controls that do not serve the goal.

## Process frameworks

18. **Design Council (2005; 2019 revision).** *The Double Diamond: A universally accepted depiction of the design process* / *Framework for Innovation.* https://www.designcouncil.org.uk/our-resources/the-double-diamond/
    Rule used: the app's phases Discover → Define → Develop → Deliver.

19. **Agile Business Consortium.** *The DSDM Agile Project Framework Handbook*, chapter 10: MoSCoW Prioritisation. https://www.agilebusiness.org/dsdm-project-framework/moscow-prioririsation.html
    Origin: Clegg, D., & Barker, R. (1994). *Case Method Fast-Track: A RAD Approach.* Addison-Wesley. ISBN 978-0-201-62432-8.
    Rule used: Must / Should / Could / Won't. In the Deliver flow, only Must-have features have to be reachable on the shortest path.

## How the rules map to the fine-tune targets

| Audit finding | Op the model should emit | Source |
|---|---|---|
| Dead end (a non-goal screen with no way forward) | `add_transition` to the goal or the next step | Nielsen #3, Norman |
| Fitts ID > 4.5 (small or far target) | `move_zone` → `bottom` (the app also enlarges S/M) | Fitts, MacKenzie, Hoober, Wobbrock |
| Navigating control below 44 px | `resize` → `L` | WCAG 2.5.5, HIG, Material |
| More than 7 options on a screen | `group_options` | Hick–Hyman, Miller, Sweller |
| Control unrelated to the goal or duplicated | `remove_element` | Krug, Nielsen #8 |
