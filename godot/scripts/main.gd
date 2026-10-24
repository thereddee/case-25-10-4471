class_name Main
extends Node
## Contrôleur de flux : salle de jeu → solution scellée → salle de jeu.
##
## Instancie les scènes, écoute leurs signaux, gère le fondu. Les scènes ne se connaissent pas.
## Structure attendue :
##   Main (Node)
##   ├── SceneHolder (Node)          -- la scène courante vit ici
##   └── Fade (CanvasLayer) › Overlay (ColorRect)

## Émis quand une nouvelle scène est en place (après le fondu).
signal scene_changed(scene: Node)

## Scène de la salle (doit avoir un script GameRoom).
@export var room_scene: PackedScene
## Scène de la solution scellée (doit avoir un script SealedSolution).
@export var solution_scene: PackedScene
## Ressource affichée par la solution scellée (vide = celle de la scène).
@export var solution_data: SolutionData
## Durée du fondu (s) à chaque changement de scène.
@export_range(0.0, 3.0, 0.05) var fade_duration: float = 0.6
## Seul trigger_id qui mène à la solution (vide = n'importe quelle sortie).
@export var solution_exit_id: StringName = &"door"

@export_group("Câblage")
@export var scene_holder: Node
@export var fade_overlay: ColorRect

var _current: Node = null
var _switching := false


func _ready() -> void:
	if fade_overlay:
		fade_overlay.color.a = 1.0
		fade_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	await _show_room()


# --- Transitions --------------------------------------------------------------------------

func _show_room() -> void:
	var scene := await _switch_to(room_scene)
	var room := scene as GameRoom
	if room == null:
		push_error("Main : room_scene n'a pas de script GameRoom.")
		return
	room.room_exited.connect(_on_room_exited.bind(room))


func _show_solution(room: GameRoom) -> void:
	var collected := room.collected_evidence()
	var total := room.evidence_total()
	var scene := await _switch_to(solution_scene)
	var solution := scene as SealedSolution
	if solution == null:
		push_error("Main : solution_scene n'a pas de script SealedSolution.")
		return
	if solution_data:
		solution.solution = solution_data
	solution.present(collected, total)
	solution.closed.connect(_on_solution_closed, CONNECT_ONE_SHOT)


## Fondu au noir, remplacement de la scène courante, fondu d'entrée. Retourne la nouvelle scène.
func _switch_to(packed: PackedScene) -> Node:
	if packed == null:
		push_error("Main : PackedScene manquante.")
		return null
	_switching = true
	await _fade(1.0)
	if _current:
		_current.queue_free()
		_current = null
	_current = packed.instantiate()
	(scene_holder if scene_holder else self).add_child(_current)
	await _fade(0.0)
	_switching = false
	scene_changed.emit(_current)
	return _current


func _fade(target_alpha: float) -> void:
	if fade_overlay == null or fade_duration <= 0.0:
		if fade_overlay:
			fade_overlay.color.a = target_alpha
		return
	var tween := create_tween()
	tween.tween_property(fade_overlay, "color:a", target_alpha, fade_duration)
	await tween.finished


# --- Signaux ------------------------------------------------------------------------------

func _on_room_exited(exit_id: StringName, room: GameRoom) -> void:
	if _switching:
		return
	if solution_exit_id != &"" and exit_id != solution_exit_id:
		return
	# Le trigger de sortie affiche d'abord son texte ; on laisse le joueur le lire.
	if room.is_dialogue_open():
		await room.dialogue_closed
	_show_solution(room)


func _on_solution_closed() -> void:
	if not _switching:
		_show_room()
