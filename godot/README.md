# Dossier 25-10-4471 — la salle de jeu en Godot 4

Implémentation Godot 4.3+ de la scène du crime : l'appartement de Julien Caron, le lendemain
matin. Vue du dessus, point-and-click au clavier. Le joueur examine la pièce, Lavoie commente
selon la progression, et la porte ne s'ouvre qu'une fois la statuette identifiée.

Ouvrir ce dossier (`godot/`) comme projet dans Godot 4.3 ou plus récent et appuyer sur F5.
Tout fonctionne avec des textures de remplacement (`PlaceholderTexture2D`) : aucun asset requis.

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

`move_left/right/up/down` (WASD + flèches), `interact` (E), `toggle_log` (Tab).
L'invite affiche automatiquement la touche liée à `interact`.

## Assets de remplacement à substituer

- Sprites : chaque `Sprite2D` utilise un `PlaceholderTexture2D` teinté via `self_modulate`.
  Remplacer `texture` par vos PNG et remettre `self_modulate` à blanc.
- Tuiles : `FloorTiles` / `WallTiles` partagent un `TileSet` 32×32 sans source. Ajouter une
  source atlas, peindre, puis supprimer `FloorPlaceholder` et `WallColliders`.
- Lumières : texture radiale générée (`GradientTexture2D`) ; remplaçable par un PNG de lumière.
- Audio : `ambient_loop`, `evidence_sfx`, `blocked_sfx` sont vides par défaut.
- Thème UI : aucun thème ; brancher un `Theme` sur `UI` suffit.
