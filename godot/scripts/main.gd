class_name Main
extends Node
## Contrôleur de flux : écran titre → salle de jeu → solution scellée → écran titre.
## Possède aussi le menu pause (Échap), actif seulement pendant la salle, et le menu
## Paramètres (volumes), ouvert depuis le titre ou la pause.
## Gère la sauvegarde : charge au titre, restaure en entrant dans la salle, autosauvegarde sur
## GameRoom.state_changed, à la sortie, au retour au titre et à la fermeture de la fenêtre.
##
## Instancie les scènes, écoute leurs signaux, gère le fondu. Les scènes ne se connaissent pas.
## Structure attendue :
##   Main (Node)
##   ├── SceneHolder (Node)          -- la scène courante vit ici
##   ├── PauseMenu (CanvasLayer)      -- scène pause_menu.tscn instanciée
##   ├── SettingsMenu (CanvasLayer)   -- scène settings_menu.tscn instanciée, après PauseMenu
##                                       pour recevoir l'input en premier
##   └── Fade (CanvasLayer) › Overlay (ColorRect)

## Émis quand une nouvelle scène est en place (après le fondu).
signal scene_changed(scene: Node)

## Écran titre (doit avoir un script TitleScreen). Vide = on démarre directement dans la salle.
@export var title_scene: PackedScene
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

@export_group("Sauvegarde")
## Faux = aucune écriture automatique (la lecture au titre reste active).
@export var autosave: bool = true
## Emplacement : le fichier est user://<save_slot>.json.
@export var save_slot: String = "save"

@export_group("Câblage")
@export var scene_holder: Node
@export var fade_overlay: ColorRect
## Menu pause (optionnel). Activé par Main uniquement quand la salle est affichée.
@export var pause_menu: PauseMenu
## Menu Paramètres (optionnel). Ouvert sur settings_requested du titre ou de la pause.
@export var settings_menu: SettingsMenu

var _current: Node = null
var _switching := false
var _save: SaveData = SaveData.new()


func _ready() -> void:
	if fade_overlay:
		fade_overlay.color.a = 1.0
		fade_overlay.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if pause_menu:
		pause_menu.enabled = false
		pause_menu.return_to_title_requested.connect(_on_return_to_title_requested)
		pause_menu.settings_requested.connect(_open_settings)
	if settings_menu:
		settings_menu.closed.connect(_on_settings_closed)
	else:
		# Sans menu, on applique quand même les volumes sauvegardés.
		AudioSettings.load_or_default().apply()
	_save = SaveStore.load_or_default(_save_path())
	if title_scene:
		await _show_title()
	else:
		await _show_room()


func _notification(what: int) -> void:
	# Fermeture de la fenêtre : on garde la position du joueur si on est dans la salle.
	if what == NOTIFICATION_WM_CLOSE_REQUEST:
		_autosave_current_room()


# --- Transitions --------------------------------------------------------------------------

func _show_title() -> void:
	var scene := await _switch_to(title_scene)
	var title := scene as TitleScreen
	if title == null:
		push_error("Main : title_scene n'a pas de script TitleScreen.")
		return
	_save = SaveStore.load_or_default(_save_path())
	title.set_save_info(not _save.is_empty(), _save_summary())
	title.start_requested.connect(_on_start_requested, CONNECT_ONE_SHOT)
	title.new_game_requested.connect(_on_new_game_requested, CONNECT_ONE_SHOT)
	title.quit_requested.connect(_on_quit_requested, CONNECT_ONE_SHOT)
	title.settings_requested.connect(_open_settings)


func _show_room() -> void:
	var scene := await _switch_to(room_scene)
	var room := scene as GameRoom
	if room == null:
		push_error("Main : room_scene n'a pas de script GameRoom.")
		return
	if not _save.is_empty():
		room.restore_state(_save)
	room.room_exited.connect(_on_room_exited.bind(room))
	room.state_changed.connect(_autosave.bind(room))
	if pause_menu:
		pause_menu.enabled = true


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
	if pause_menu:
		pause_menu.enabled = false  # dépause aussi si on quitte la salle en plein menu
	if settings_menu:
		settings_menu.close()
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
	_save.case_closed = true
	_autosave(room)
	# Le trigger de sortie affiche d'abord son texte ; on laisse le joueur le lire.
	if room.is_dialogue_open():
		await room.dialogue_closed
	_show_solution(room)


func _on_solution_closed() -> void:
	if _switching:
		return
	if title_scene:
		_show_title()
	else:
		_show_room()


func _on_start_requested() -> void:
	if not _switching:
		_show_room()


func _on_new_game_requested() -> void:
	if _switching:
		return
	SaveStore.clear(_save_path())
	_save = SaveData.new()
	_show_room()


func _on_quit_requested() -> void:
	get_tree().quit()


func _open_settings() -> void:
	if settings_menu and not _switching:
		settings_menu.open()


## Rend le focus clavier à l'écran qui a ouvert les paramètres.
func _on_settings_closed() -> void:
	if pause_menu and pause_menu.is_paused():
		pause_menu.focus_default()
	elif _current and _current.has_method("focus_default"):
		_current.focus_default()


func _on_return_to_title_requested() -> void:
	if _switching:
		return
	_autosave_current_room()
	if title_scene:
		_show_title()
	else:
		_show_room()


# --- Sauvegarde ---------------------------------------------------------------------------

func _save_path() -> String:
	return SaveStore.path_for_slot(save_slot)


## Capture l'état de `room` dans _save et l'écrit sur disque (si autosave).
func _autosave(room: GameRoom) -> void:
	if room == null or not is_instance_valid(room):
		return
	room.capture_state(_save)
	if not autosave:
		return
	_save.saved_at = Time.get_datetime_string_from_system(false, true)
	SaveStore.save(_save, _save_path())


func _autosave_current_room() -> void:
	var room := _current as GameRoom
	if room:
		_autosave(room)


## Résumé affiché sous le titre : « 3 preuves · dossier clos · 2026-10-24 14:02 ».
func _save_summary() -> String:
	if _save.is_empty():
		return ""
	var parts: Array[String] = []
	parts.append("%d preuve%s" % [_save.collected_evidence.size(), "s" if _save.collected_evidence.size() > 1 else ""])
	if _save.case_closed:
		parts.append("dossier clos")
	if _save.saved_at != "":
		parts.append(_save.saved_at)
	return " · ".join(parts)
