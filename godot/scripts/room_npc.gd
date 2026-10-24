class_name RoomNPC
extends CharacterBody2D
## Un personnage présent dans la salle (ici le sgt-dét. Lavoie).
##
## Choisit une réplique dans `lines` selon la progression de l'enquête (0.0 à 1.0) que la
## racine lui passe. Aucune connaissance de l'UI. Structure attendue :
##   NPC (CharacterBody2D, calque 3 « NPC »)
##   ├── Shape  (CollisionShape2D)
##   └── Sprite (Sprite2D)

## Émis quand le PNJ parle. La racine affiche `line` dans la boîte de dialogue.
signal talked(npc: RoomNPC, line: String)

## Nom affiché comme locuteur.
@export var npc_name: String = "Sgt-dét. Lavoie"

## Répliques ordonnées : index 0 = aucune preuve trouvée, dernier index = tout trouvé.
## La progression est projetée linéairement sur ce tableau.
@export_multiline var lines: Array[String] = []

## Teinte appliquée au Sprite quand le PNJ est visé.
@export var highlight_color: Color = Color(0.8, 0.9, 1.0)

@onready var _sprite: Sprite2D = get_node_or_null(^"Sprite") as Sprite2D


func display_name() -> String:
	return npc_name


func prompt_text() -> String:
	return "Parler à %s" % npc_name


func set_focused(focused: bool) -> void:
	if _sprite:
		_sprite.modulate = highlight_color if focused else Color.WHITE


## Fait parler le PNJ. `progress` ∈ [0, 1] = part des preuves collectées.
func talk(progress: float) -> void:
	if lines.is_empty():
		push_warning("%s : aucune réplique configurée." % name)
		return
	var last := lines.size() - 1
	var index := clampi(roundi(clampf(progress, 0.0, 1.0) * last), 0, last)
	talked.emit(self, lines[index])
