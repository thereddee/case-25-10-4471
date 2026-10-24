# Dossier 25-10-4471 — la salle de jeu en Godot 4

Implémentation Godot 4.3+ de la scène du crime : l'appartement de Julien Caron, le lendemain
matin. Vue du dessus, point-and-click au clavier. Le joueur examine la pièce, Lavoie commente
selon la progression, et la porte ne s'ouvre qu'une fois la statuette identifiée.

Ouvrir ce dossier (`godot/`) comme projet dans Godot 4.3 ou plus récent et appuyer sur F5.
Tout fonctionne avec des textures de remplacement (`PlaceholderTexture2D`) : aucun asset requis.

## Flux des scènes (`scenes/main.tscn`)

```
Main (Node)                                     main.gd — contrôleur de flux
├── SceneHolder (Node)                          la scène courante est instanciée ici
├── PauseMenu (instance de pause_menu.tscn)     menu pause, actif seulement dans la salle
├── SettingsMenu (instance de settings_menu.tscn) volumes ; placé après PauseMenu pour recevoir l'input d'abord
└── Fade (CanvasLayer, layer 100)
    └── Overlay (ColorRect)                     fondu au noir entre les scènes
```

`Main` affiche d'abord `title_screen.tscn` et attend `TitleScreen.start_requested` (bouton,
E ou Entrée ; `quit_requested` ferme le jeu, le bouton Quitter est masqué sur le web). Il
instancie ensuite `game_room.tscn` et écoute `GameRoom.room_exited(exit_id)`. Quand `exit_id`
vaut `solution_exit_id` (défaut `door`), il attend la fermeture du dialogue de sortie
(`dialogue_closed`), fond au noir, remplace la salle par `sealed_solution.tscn`, lui passe le
récapitulatif des preuves via `present(collected, total)`, puis écoute `closed` pour revenir à
l'écran titre. Les trois scènes ne se connaissent pas ; seul `Main` les connaît.

| Propriété de `Main` | Défaut | Note |
|---|---|---|
| `title_scene` | `title_screen.tscn` | Vide = on démarre directement dans la salle |
| `room_scene` / `solution_scene` | les deux `.tscn` | PackedScene interchangeables |
| `solution_data` | vide | Remplace la ressource de la scène de solution si assignée |
| `fade_duration` | `0.6` | 0 = changement instantané |
| `solution_exit_id` | `door` | Vide = n'importe quelle sortie mène à la solution |
| `scene_holder`, `fade_overlay` | NodePath | |
| `pause_menu` | NodePath | Optionnel ; Main l'active en entrant dans la salle, le désactive ailleurs |
| `settings_menu` | NodePath | Optionnel ; ouvert sur `settings_requested` du titre ou de la pause. Sans lui, Main applique quand même les volumes sauvegardés |

## Menu pause (`scenes/pause_menu.tscn`)

```
PauseMenu (CanvasLayer, layer 50, process_mode Always)   pause_menu.gd
└── Root (Control, plein écran, caché)
    ├── Dim (ColorRect)                         assombrit le jeu
    └── Center › Panel › Margin › VBox
        ├── Title (Label)                       « Pause »
        ├── ResumeButton (Button)               « Reprendre »
        ├── SettingsButton (Button)             « Paramètres »
        ├── TitleButton (Button)                « Retour au titre »
        └── Hint (Label)
```

Échap met `get_tree().paused` à vrai et affiche le menu ; Échap ou Reprendre dépause.
« Retour au titre » dépause d'abord puis émet `return_to_title_requested`, que `Main` écoute pour
revenir à l'écran titre avec le fondu habituel. Le menu tourne en `PROCESS_MODE_ALWAYS` ; tout le
reste hérite du mode par défaut et se fige. La propriété `enabled` (gérée par `Main`) bloque la
touche hors de la salle et dépause si on la coupe en plein menu. Signaux : `paused`, `resumed`,
`settings_requested`, `return_to_title_requested`. Libellés exportés : `title_text`, `resume_label`,
`settings_label`, `title_label_text`.

## Menu Paramètres (`scenes/settings_menu.tscn`)

```
SettingsMenu (CanvasLayer, layer 60, process_mode Always)   settings_menu.gd
├── PreviewPlayer (AudioStreamPlayer, bus SFX)  joue `sfx_preview` au relâchement du slider Effets
└── Root (Control, plein écran, caché)
    ├── Dim (ColorRect)
    └── Center › Panel › Margin › VBox
        ├── Title (Label)                       « Paramètres »
        ├── MasterRow / MusicRow / SfxRow (HBoxContainer) › Name (Label), Slider (HSlider), Value (Label)
        ├── BackButton (Button)                 « Retour »
        └── Hint (Label)
```

Trois bus dans `default_bus_layout.tres` : `Master`, `Music` (AmbientPlayer de la salle) et
`SFX` (SfxPlayer, aperçu). Les sliders vont de 0 à 1 (linéaire), convertis en dB à l'application ;
sous 0,1 % le bus est coupé plutôt que mis à -80 dB. Les valeurs sont appliquées en direct et
sauvegardées à la fermeture dans `user://settings.cfg`, section `[audio]`.

`scripts/audio_settings.gd` (`AudioSettings`, RefCounted) porte la persistance et l'application,
sans UI : `load_or_default()`, `save()`, `apply()`, `set_volume(bus, linear)`. Pour ajouter un bus,
l'ajouter à `AudioSettings.BUSES`, au `default_bus_layout.tres`, et câbler une ligne de plus dans
le menu (`_rows` dans `settings_menu.gd`).

Ouvert depuis l'écran titre (bouton Paramètres) ou le menu pause (le jeu reste en pause). Tant
qu'il est ouvert il avale l'input non géré, donc E ou Échap n'atteignent pas l'écran dessous ;
Échap ou Retour le ferme et `Main` rend le focus clavier à l'écran d'origine (`focus_default()`).
Signaux : `opened`, `closed`, `volume_changed(bus, linear)`. Exports : `title_text`, `back_label`,
`sfx_preview`, et les NodePath de l'UI.

## Écran titre (`scenes/title_screen.tscn`)

```
TitleScreen (Control)                           title_screen.gd
├── Background (ColorRect)
└── Center (CenterContainer) › Panel (PanelContainer) › Margin › VBox
    ├── Unit (Label)                            « Section des crimes majeurs »
    ├── Title (Label)                           « Dossier 25-10-4471 — Caron, Julien »
    ├── Subtitle (Label)
    ├── StartButton (Button)                    « Ouvrir le dossier »
    ├── SettingsButton (Button)                 « Paramètres »
    ├── QuitButton (Button)                     masqué si OS.has_feature("web")
    └── Hint (Label)
```

Signaux : `start_requested`, `settings_requested`, `quit_requested`. Textes et libellés sont des
`@export` (`unit_text`, `title_text`, `subtitle_text`, `start_label`, `settings_label`, `quit_label`) ; `start_on_interact`
permet de lancer avec E / Entrée. Les nœuds UI sont des NodePath optionnels.

## Solution scellée (`scenes/sealed_solution.tscn`)

```
SealedSolution (Control)                        sealed_solution.gd
├── Background (ColorRect)
└── Center (CenterContainer) › Envelope (PanelContainer) › Margin › VBox
    ├── Title (Label)
    ├── Recap (Label)                           « Preuves réunies : 8 sur 8 »
    ├── SealButton (Button)                     « Briser le sceau »
    ├── Content (VBoxContainer, caché)
    │   ├── Verdict (Label)
    │   ├── Entries (RichTextLabel, bbcode)     chronologie révélée ligne par ligne
    │   └── Quote (Label)
    └── Hint (Label)
```

Le joueur brise le sceau (bouton, E ou clic), puis chaque appui sur E révèle la ligne suivante.
Une fois la dernière ligne lue, la citation de Lavoie apparaît et un dernier appui émet `closed`.
Signaux : `seal_broken`, `fully_revealed`, `closed`.

| Propriété | Défaut | Note |
|---|---|---|
| `solution` | `resources/sealed_solution.tres` | Ressource `SolutionData` : `title`, `seal_text`, `verdict`, `entries` (bbcode), `closing_quote`, `quote_author` |
| `require_seal_break` | `true` | Faux = le contenu s'ouvre tout seul |
| `auto_reveal` / `auto_reveal_interval` | `false` / `0.0` | Défilement automatique, délai en secondes entre les lignes |
| `title_label` … `hint_label` | NodePath | Tous optionnels |

## Arbre de scène (`scenes/game_room.tscn`)

```
GameRoom (Node2D)                               game_room.gd  — racine, état de l'enquête, câblage
├── Environment (Node2D)
│   ├── FloorTiles (TileMapLayer)               TileSet 32×32 vide, prêt à peindre
│   ├── WallTiles (TileMapLayer)                même TileSet ; physics layer 0 → calque World
│   ├── FloorPlaceholder (Polygon2D)            plancher temporaire, z_index -10
│   ├── Rug (Polygon2D)                         tapis sous la table
│   ├── BloodStain (Polygon2D)                  tache à droite de la chaise du DM
│   ├── WallColliders (StaticBody2D)            4 murs tant que WallTiles n'est pas peint
│   │   ├── Top / Bottom / Left / Right (CollisionShape2D)
│   └── Props (Node2D)                          meubles solides : StaticBody2D + Shape + Sprite
│       ├── GameTable, DMChair, Shelf, Counter
├── Lighting (Node2D)
│   ├── Ambient (CanvasModulate)                pénombre du matin
│   ├── CeilingLamp (PointLight2D)              au-dessus de la table
│   └── StreetGlow (PointLight2D)               lumière froide par la fenêtre
├── Interactables (Node2D)                      un Interactable (Area2D) par pièce à conviction
│   ├── PhonePlaylist, TreasuryLedger, DMNotebook, DMScreen, CharacterSheet  (sur la table)
│   ├── PizzaBox (sur le comptoir), Satchel (au sol), BronzeDragon (sur la tablette)
│   │   └── chacun : Shape (CollisionShape2D) + Sprite (Sprite2D)
├── Triggers (Node2D)                           RoomTrigger (Area2D) + Shape
│   ├── DoorTrigger                             sortie ; exige bronze_dragon
│   ├── WindowTrigger                           texte d'ambiance (l'auto de Samuel)
│   └── BloodStainTrigger                       texte d'ambiance, une seule fois
├── NPCs (Node2D)
│   └── Lavoie (CharacterBody2D)                room_npc.gd ; Shape + Sprite
├── Player (CharacterBody2D)                    room_player.gd
│   ├── Shape (CollisionShape2D)                capsule 10 × 28
│   ├── Sprite (Sprite2D)
│   ├── InteractRay (RayCast2D)                 vise Interactable | NPC, collide_with_areas
│   └── Camera (Camera2D)                       limites = taille de la pièce
├── Audio (Node)
│   ├── AmbientPlayer (AudioStreamPlayer)
│   └── SfxPlayer (AudioStreamPlayer)
└── UI (CanvasLayer)
    ├── HelpLabel (Label)
    ├── InteractPrompt (Label)                  « [E] Examiner Téléphone de Julien »
    ├── DialogueBox (PanelContainer) › Margin › VBox › Speaker (Label), Text (RichTextLabel), Hint (Label)
    └── EvidenceLog (PanelContainer) › Margin › VBox › Counter (Label), List (ItemList)
```

## Scripts (`scripts/`)

| Script | Classe | Rôle |
|---|---|---|
| `game_room.gd` | `GameRoom` | Racine. Connecte les signaux des enfants, possède la liste des preuves, pilote l'UI, formate les textes. |
| `interactable.gd` | `Interactable` | Area2D examinable. Émet `interacted` et `focus_changed`, ne touche à rien d'autre. |
| `room_player.gd` | `RoomPlayer` | Déplacement + RayCast2D. Émet `interact_target_changed` et `interact_requested`. |
| `room_npc.gd` | `RoomNPC` | Choisit une réplique selon la progression (0 → 1). Émet `talked`. |
| `room_trigger.gd` | `RoomTrigger` | Zone environnementale. Émet `player_entered` / `player_exited`. |
| `evidence_data.gd` | `EvidenceData` (Resource) | Données d'une preuve : id, titre, description, prérequis. |
| `music_timeline.gd` | `MusicTimeline` (Resource) | La liste de lecture ; calcule l'heure de la pause (22:05). |
| `main.gd` | `Main` | Contrôleur de flux : titre → salle → solution scellée → titre, avec fondu. |
| `title_screen.gd` | `TitleScreen` | Écran titre ; boutons Ouvrir / Quitter, émet `start_requested`. |
| `pause_menu.gd` | `PauseMenu` | Menu pause (Échap) ; Reprendre, Paramètres, Retour au titre. |
| `settings_menu.gd` | `SettingsMenu` | Menu Paramètres ; sliders Général / Musique / Effets. |
| `audio_settings.gd` | `AudioSettings` (RefCounted) | Volumes des bus, persistés dans `user://settings.cfg`. |
| `sealed_solution.gd` | `SealedSolution` | Écran de la solution ; sceau, révélation ligne par ligne. |
| `solution_data.gd` | `SolutionData` (Resource) | Verdict, chronologie et citation de la solution. |

Flux d'une interaction : `RoomPlayer.interact_requested(target)` → `GameRoom` appelle
`Interactable.interact()` → `Interactable.interacted(self)` → `GameRoom` vérifie les prérequis,
formate `description` avec `build_format_context()`, ouvre le dialogue, collecte la preuve, émet
`evidence_collected`. Aucun enfant ne connaît l'UI ni l'état du jeu.

Signaux exposés par la racine pour le reste du jeu (autoload, gestionnaire de scènes) :
`evidence_collected(id, total, maximum)`, `all_evidence_collected`, `room_exited(exit_id)`,
`dialogue_opened(speaker, text)`, `dialogue_closed`.

## Paramètres d'inspecteur

### GameRoom

| Groupe | Propriété | Défaut | Note |
|---|---|---|---|
| Dossier | `music_timeline` | `resources/music_timeline.tres` | Source de `{pause_time}`, `{elapsed_minutes}`, `{paused_track}`, `{paused_offset}`, `{music_start}` |
| Dossier | `scream_time` | `21:12` | `{scream_time}` |
| Dossier | `departure_time` | `21:30` | `{departure_time}` |
| Dossier | `ledger_time` | `20:50` | `{ledger_time}` |
| Dossier | `pizza_slices_at_closing` / `pizza_slices_found` | `2` / `1` | `{slices_at_closing}`, `{slices_found}`, `{slices_missing}` |
| Câblage | `player`, `interactables_root`, `triggers_root`, `npcs_root` | NodePath | Déplacer un nœud = réassigner ici, pas de `$` codé en dur |
| Câblage | `exit_trigger_id` | `door` | Le trigger qui émet `room_exited` |
| Câblage | `narrator_name` | `Constat` | Locuteur des descriptions |
| Audio | `ambient_loop`, `evidence_sfx`, `blocked_sfx` | vide | Glisser des AudioStream ; vide = silence |
| Audio | `ambient_player`, `sfx_player` | NodePath | |
| UI | `prompt_label`, `dialogue_box`, `dialogue_speaker`, `dialogue_text`, `evidence_log`, `evidence_list`, `evidence_counter` | NodePath | Tous optionnels : un NodePath vide désactive proprement cette partie de l'UI |

Les marqueurs `{cle}` fonctionnent dans `EvidenceData.description`, `RoomTrigger.enter_text`
et `RoomNPC.lines`. Ajouter une clé dans `build_format_context()` la rend disponible partout.

### Interactable

`evidence` (EvidenceData), `prompt_verb` (« Examiner »), `one_shot`, `highlight_color`.

### EvidenceData (`resources/evidence/*.tres`)

| id | Titre | Prérequis |
|---|---|---|
| `phone_playlist` | Téléphone de Julien | — |
| `dm_notebook` | Bloc-notes du DM | — |
| `pizza_box` | Boîte de pizza végétarienne | — |
| `treasury_ledger` | Registre du Trésor de l'Aube | — |
| `character_sheet` | Feuille de personnage : Ser Aldric | — |
| `dm_screen` | Écran du DM | — |
| `satchel` | Cartable de Julien | — |
| `bronze_dragon` | Dragon de bronze | `phone_playlist`, `character_sheet` |

### MusicTimeline (`resources/music_timeline.tres`)

`start_time` = `19:40`, `track_durations_seconds` = 38 pistes (les 37 premières totalisent 143:13),
`paused_track_index` = 37 (piste 38), `paused_offset_seconds` = 107 (1:47). `pause_time()` → `22:05`.

### RoomPlayer

`move_speed` (140 px/s), `interact_distance` (40 px), `can_move`, `initial_facing`.

### RoomNPC

`npc_name`, `lines` (Array[String], index 0 = rien trouvé, dernier = tout trouvé), `highlight_color`.

### RoomTrigger

`trigger_id`, `required_evidence`, `enter_text`, `blocked_text`, `one_shot`.

## Calques de collision (nommés dans `project.godot`)

| Bit | Nom | Qui est dessus (layer) | Qui le détecte (mask) |
|---|---|---|---|
| 1 | World | WallColliders, Props, WallTiles (physics layer 0) | Player, NPC |
| 2 | Player | Player | Triggers |
| 3 | NPC | Lavoie | Player, InteractRay |
| 4 | Interactable | tous les Interactable | InteractRay |
| 5 | Trigger | tous les RoomTrigger | — |

Valeurs : Player `layer=2 mask=5` · InteractRay `mask=12`, `collide_with_areas=true` ·
Interactable `layer=8 mask=0` · Trigger `layer=16 mask=2` · NPC `layer=4 mask=1` · solides `layer=1 mask=0`.

## Entrées (`project.godot`)

`move_left/right/up/down` (WASD + flèches), `interact` (E), `toggle_log` (Tab), `pause` (Échap).
L'invite affiche automatiquement la touche liée à `interact`.

## Assets de remplacement à substituer

- Sprites : chaque `Sprite2D` utilise un `PlaceholderTexture2D` teinté via `self_modulate`.
  Remplacer `texture` par vos PNG et remettre `self_modulate` à blanc.
- Tuiles : `FloorTiles` / `WallTiles` partagent un `TileSet` 32×32 sans source. Ajouter une
  source atlas, peindre, puis supprimer `FloorPlaceholder` et `WallColliders`.
- Lumières : texture radiale générée (`GradientTexture2D`) ; remplaçable par un PNG de lumière.
- Audio : `ambient_loop`, `evidence_sfx`, `blocked_sfx` (salle) et `sfx_preview` (paramètres) sont vides par défaut.
- Thème UI : aucun thème ; brancher un `Theme` sur `UI` suffit.
