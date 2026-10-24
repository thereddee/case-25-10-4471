class_name Interactable
extends Area2D
## Un objet de la salle que le joueur peut examiner.
##
## Ne touche ni à l'UI ni à l'état du jeu : il annonce ce qui lui arrive par des signaux
## et laisse la racine (GameRoom) décider quoi en faire. Structure attendue :
##   Interactable (Area2D, calque 4 « Interactable »)
##   ├── Shape  (CollisionShape2D)
##   └── Sprite (Sprite2D)  -- optionnel, utilisé pour la surbrillance

## Émis quand le joueur appuie sur « interagir » en visant cet objet.
signal interacted(interactable: Interactable)
## Émis quand le rayon du joueur commence (true) ou arrête (false) de viser cet objet.
signal focus_changed(interactable: Interactable, focused: bool)

## Données de la pièce à conviction associée. Peut rester vide pour un simple décor commenté.
@export var evidence: EvidenceData

## Verbe affiché dans l'invite : « Examiner », « Ouvrir », « Lire »...
@export var prompt_verb: String = "Examiner"

## Si vrai, l'objet ne répond plus après la première interaction réussie.
@export var one_shot: bool = false

## Teinte appliquée au Sprite quand l'objet est visé.
@export var highlight_color: Color = Color(1.0, 0.9, 0.55)

var _used := false
@onready var _sprite: Sprite2D = get_node_or_null(^"Sprite") as Sprite2D


func _ready() -> void:
	# Garde-fou : l'objet doit être détectable par le RayCast2D du joueur (calque 4).
	if collision_layer == 0:
		push_warning("%s : collision_layer vide, le joueur ne pourra pas le viser." % name)


## Nom lisible, utilisé par l'invite et le journal.
func display_name() -> String:
	return evidence.title if evidence else String(name)


## Texte complet de l'invite (« Examiner Téléphone de Julien »).
func prompt_text() -> String:
	return "%s %s" % [prompt_verb, display_name()]


## Appelé par la racine quand le rayon du joueur entre/sort de l'objet.
func set_focused(focused: bool) -> void:
	if _sprite:
		_sprite.modulate = highlight_color if focused else Color.WHITE
	focus_changed.emit(self, focused)


## Appelé par la racine quand le joueur interagit. Respecte `one_shot`.
func interact() -> void:
	if one_shot and _used:
		return
	interacted.emit(self)


## À appeler par la racine une fois la pièce réellement collectée
## (pas quand elle était verrouillée), pour que `one_shot` prenne effet.
func mark_used() -> void:
	_used = true
