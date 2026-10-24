class_name GameRoom
extends Node2D
## Racine de la salle de jeu : l'appartement de Julien Caron, le lendemain matin.
##
## Rôle : câbler les enfants entre eux et posséder l'état de l'enquête (preuves collectées).
## Les enfants (Interactable, RoomNPC, RoomTrigger, RoomPlayer) ne se connaissent pas ;
## ils émettent des signaux, la racine arbitre et pilote l'UI. Tout ce qui est propre
## au dossier (heures, pizza, musique) vient de ressources ou d'@export, jamais du code.
##
## Les nœuds sont référencés par @export (NodePath résolu dans l'inspecteur) pour pouvoir
## réorganiser l'arbre sans casser le script.

## Émis à chaque pièce collectée. `total`/`maximum` servent aux barres de progression.
signal evidence_collected(id: StringName, total: int, maximum: int)
## Émis quand toutes les pièces de la salle ont été trouvées.
signal all_evidence_collected
## Émis quand le joueur franchit la zone de sortie avec les prérequis remplis.
signal room_exited(exit_id: StringName)
## Émis à l'ouverture d'un texte (preuve, PNJ, zone). Utile pour un autoload de journal/voix.
signal dialogue_opened(speaker: String, text: String)
## Émis à la fermeture de la boîte de dialogue.
signal dialogue_closed

@export_group("Dossier")
## Liste de lecture du téléphone ; calcule l'heure réelle du décès.
@export var music_timeline: MusicTimeline
## Heure du cri de Karine, retenue à tort par la police.
@export var scream_time: String = "21:12"
## Heure officielle de fin de séance, quand tout le monde est parti.
@export var departure_time: String = "21:30"
## Heure à laquelle Julien a remis le registre du Trésor aux joueurs.
@export var ledger_time: String = "20:50"
## Pointes de pizza végétarienne restantes à la fermeture de la boîte.
@export_range(0, 12) var pizza_slices_at_closing: int = 2
## Pointes de pizza végétarienne trouvées le matin.
@export_range(0, 12) var pizza_slices_found: int = 1

@export_group("Câblage de la scène")
## Le joueur. Doit avoir le script room_player.gd.
@export var player: RoomPlayer
## Parent direct de tous les Interactable.
@export var interactables_root: Node
## Parent direct de tous les RoomTrigger.
@export var triggers_root: Node
## Parent direct de tous les RoomNPC.
@export var npcs_root: Node
## trigger_id de la zone qui fait sortir de la salle.
@export var exit_trigger_id: StringName = &"door"
## Locuteur affiché pour les descriptions de preuves.
@export var narrator_name: String = "Constat"

@export_group("Audio")
## Ambiance jouée en boucle au chargement (vide = silence).
@export var ambient_loop: AudioStream
## Son joué à chaque preuve collectée.
@export var evidence_sfx: AudioStream
## Son joué quand une zone ou une preuve est verrouillée.
@export var blocked_sfx: AudioStream
@export var ambient_player: AudioStreamPlayer
@export var sfx_player: AudioStreamPlayer

@export_group("UI")
@export var prompt_label: Label
@export var dialogue_box: Control
@export var dialogue_speaker: Label
@export var dialogue_text: RichTextLabel
@export var evidence_log: Control
@export var evidence_list: ItemList
@export var evidence_counter: Label

## Preuves collectées, dans l'ordre.
var _collected: Array[StringName] = []
## Toutes les preuves présentes dans la salle (déduites des Interactable au _ready).
var _all_evidence_ids: Array[StringName] = []
var _dialogue_open := false


func _ready() -> void:
	_validate_wiring()
	_wire_player()
	_wire_interactables()
	_wire_triggers()
	_wire_npcs()
	_setup_ui()
	_start_ambient()


func _unhandled_input(event: InputEvent) -> void:
	# Ordre d'appel : les enfants reçoivent _unhandled_input avant la racine. Pendant un
	# dialogue le joueur ignore « interact » (can_move = false), donc c'est nous qui fermons.
	if _dialogue_open and (event.is_action_pressed("interact") or event.is_action_pressed("ui_accept")):
		close_dialogue()
		get_viewport().set_input_as_handled()
	elif event.is_action_pressed("toggle_log") and evidence_log:
		evidence_log.visible = not evidence_log.visible
		get_viewport().set_input_as_handled()


# --- API publique -------------------------------------------------------------------------

## Copie des identifiants collectés.
func collected_evidence() -> Array[StringName]:
	return _collected.duplicate()


## Vrai si la pièce `id` est dans le journal.
func has_evidence(id: StringName) -> bool:
	return _collected.has(id)


## Nombre total de pièces présentes dans la salle.
func evidence_total() -> int:
	return _all_evidence_ids.size()


## Vrai tant qu'une boîte de dialogue est affichée.
func is_dialogue_open() -> bool:
	return _dialogue_open


## Progression de l'enquête dans [0, 1].
func progress() -> float:
	if _all_evidence_ids.is_empty():
		return 0.0
	return float(_collected.size()) / float(_all_evidence_ids.size())


## Valeurs injectées dans les descriptions via String.format() : « {pause_time} », etc.
## Ajouter une clé ici suffit pour la rendre disponible à toutes les ressources EvidenceData.
func build_format_context() -> Dictionary:
	var context := {
		"scream_time": scream_time,
		"departure_time": departure_time,
		"ledger_time": ledger_time,
		"slices_at_closing": pizza_slices_at_closing,
		"slices_found": pizza_slices_found,
		"slices_missing": pizza_slices_at_closing - pizza_slices_found,
	}
	if music_timeline:
		context["music_start"] = music_timeline.start_time
		context["pause_time"] = music_timeline.pause_time()
		context["elapsed_minutes"] = music_timeline.elapsed_minutes()
		context["paused_track"] = music_timeline.paused_track_number()
		context["paused_offset"] = music_timeline.paused_offset_label()
	return context


## Affiche un texte et gèle le joueur jusqu'à la fermeture.
func open_dialogue(speaker: String, text: String) -> void:
	_dialogue_open = true
	if player:
		player.can_move = false
	if dialogue_speaker:
		dialogue_speaker.text = speaker
	if dialogue_text:
		dialogue_text.text = text
	if dialogue_box:
		dialogue_box.visible = true
	if prompt_label:
		prompt_label.visible = false
	dialogue_opened.emit(speaker, text)


func close_dialogue() -> void:
	_dialogue_open = false
	if dialogue_box:
		dialogue_box.visible = false
	if player:
		player.can_move = true
		_refresh_prompt(player.current_target())
	dialogue_closed.emit()


# --- Câblage ------------------------------------------------------------------------------

func _validate_wiring() -> void:
	for pair in [[player, "player"], [interactables_root, "interactables_root"],
			[triggers_root, "triggers_root"], [npcs_root, "npcs_root"]]:
		if pair[0] == null:
			push_warning("GameRoom : « %s » n'est pas assigné dans l'inspecteur." % pair[1])


func _wire_player() -> void:
	if player == null:
		return
	player.interact_target_changed.connect(_on_player_target_changed)
	player.interact_requested.connect(_on_player_interact_requested)


func _wire_interactables() -> void:
	for node in _children_of(interactables_root):
		var interactable := node as Interactable
		if interactable == null:
			continue
		interactable.interacted.connect(_on_interactable_interacted)
		if interactable.evidence and interactable.evidence.id != &"":
			if _all_evidence_ids.has(interactable.evidence.id):
				push_warning("GameRoom : id de preuve dupliqué « %s »." % interactable.evidence.id)
			else:
				_all_evidence_ids.append(interactable.evidence.id)


func _wire_triggers() -> void:
	for node in _children_of(triggers_root):
		var trigger := node as RoomTrigger
		if trigger:
			trigger.player_entered.connect(_on_trigger_entered)


func _wire_npcs() -> void:
	for node in _children_of(npcs_root):
		var npc := node as RoomNPC
		if npc:
			npc.talked.connect(_on_npc_talked)


func _children_of(root: Node) -> Array[Node]:
	return root.get_children() if root else ([] as Array[Node])


func _setup_ui() -> void:
	if dialogue_box:
		dialogue_box.visible = false
	if prompt_label:
		prompt_label.visible = false
	if evidence_log:
		evidence_log.visible = false
	_refresh_counter()


func _start_ambient() -> void:
	if ambient_player and ambient_loop:
		ambient_player.stream = ambient_loop
		ambient_player.play()


# --- Réactions aux signaux ----------------------------------------------------------------

func _on_player_target_changed(target: Node2D) -> void:
	# On rafraîchit la surbrillance de l'ancienne et de la nouvelle cible.
	for child in _children_of(interactables_root) + _children_of(npcs_root):
		if child.has_method("set_focused"):
			child.set_focused(child == target)
	_refresh_prompt(target)


func _on_player_interact_requested(target: Node2D) -> void:
	if _dialogue_open:
		return
	if target is Interactable:
		(target as Interactable).interact()
	elif target is RoomNPC:
		(target as RoomNPC).talk(progress())


func _on_interactable_interacted(interactable: Interactable) -> void:
	var evidence := interactable.evidence
	if evidence == null:
		open_dialogue(narrator_name, "Rien d'utile ici.")
		return

	var missing := evidence.missing_requirements(_collected)
	if not missing.is_empty():
		_play_sfx(blocked_sfx)
		open_dialogue(narrator_name, evidence.locked_text)
		return

	interactable.mark_used()
	open_dialogue(narrator_name, evidence.description.format(build_format_context()))
	_collect(evidence)


func _on_trigger_entered(trigger: RoomTrigger) -> void:
	if not trigger.can_fire():
		return
	var missing := trigger.missing_evidence(_collected)
	if not missing.is_empty():
		_play_sfx(blocked_sfx)
		if trigger.blocked_text != "":
			open_dialogue(narrator_name, trigger.blocked_text)
		return

	trigger.mark_fired()
	if trigger.enter_text != "":
		open_dialogue(narrator_name, trigger.enter_text.format(build_format_context()))
	if trigger.trigger_id == exit_trigger_id:
		room_exited.emit(trigger.trigger_id)


func _on_npc_talked(npc: RoomNPC, line: String) -> void:
	open_dialogue(npc.display_name(), line.format(build_format_context()))


# --- Helpers ------------------------------------------------------------------------------

func _collect(evidence: EvidenceData) -> void:
	if evidence.id == &"" or _collected.has(evidence.id):
		return
	_collected.append(evidence.id)
	_play_sfx(evidence_sfx)
	if evidence_list:
		evidence_list.add_item(evidence.title, evidence.icon)
	_refresh_counter()
	evidence_collected.emit(evidence.id, _collected.size(), _all_evidence_ids.size())
	if _collected.size() >= _all_evidence_ids.size():
		all_evidence_collected.emit()


func _refresh_prompt(target: Node2D) -> void:
	if prompt_label == null:
		return
	if target and target.has_method("prompt_text") and not _dialogue_open:
		prompt_label.text = "[%s] %s" % [_interact_key_label(), target.prompt_text()]
		prompt_label.visible = true
	else:
		prompt_label.visible = false


func _refresh_counter() -> void:
	if evidence_counter:
		evidence_counter.text = "Preuves : %d / %d" % [_collected.size(), _all_evidence_ids.size()]


func _play_sfx(stream: AudioStream) -> void:
	if sfx_player and stream:
		sfx_player.stream = stream
		sfx_player.play()


## Nom de la première touche liée à « interact », pour l'invite.
func _interact_key_label() -> String:
	for event in InputMap.action_get_events("interact"):
		if event is InputEventKey:
			var key := event as InputEventKey
			if key.physical_keycode != KEY_NONE:
				return OS.get_keycode_string(DisplayServer.keyboard_get_keycode_from_physical(key.physical_keycode))
			return OS.get_keycode_string(key.keycode)
	return "Interagir"
