class_name SealedSolution
extends Control
## Écran de la solution scellée. S'ouvre après `GameRoom.room_exited`.
##
## Le joueur brise le sceau, puis révèle la chronologie une ligne à la fois (touche
## « interact » / ui_accept, ou clic). Aucune connaissance de la salle : le contrôleur de
## flux (Main) l'instancie, appelle `present()` et écoute `closed`. Structure attendue :
##   SealedSolution (Control)
##   └── Center › Envelope (PanelContainer) › Margin › VBox
##       ├── Title (Label)
##       ├── Recap (Label)                 -- « 8 preuves sur 8 »
##       ├── SealButton (Button)           -- « Briser le sceau »
##       ├── Content (VBoxContainer)       -- caché jusqu'à l'ouverture
##       │   ├── Verdict (Label)
##       │   ├── Entries (RichTextLabel)
##       │   └── Quote (Label)
##       └── Hint (Label)

## Émis quand le sceau est brisé.
signal seal_broken
## Émis quand la dernière ligne est révélée.
signal fully_revealed
## Émis quand le joueur ferme l'écran après la révélation complète.
signal closed

## Données affichées.
@export var solution: SolutionData

## Si vrai, le sceau doit être brisé à la main ; sinon le contenu s'ouvre tout seul.
@export var require_seal_break: bool = true

## Délai (s) entre deux lignes quand `auto_reveal` est actif. 0 = tout d'un coup.
@export_range(0.0, 5.0, 0.1) var auto_reveal_interval: float = 0.0

## Si vrai, les lignes défilent seules ; sinon une par appui.
@export var auto_reveal: bool = false

@export_group("UI")
@export var title_label: Label
@export var recap_label: Label
@export var seal_button: Button
@export var content: Control
@export var verdict_label: Label
@export var entries_label: RichTextLabel
@export var quote_label: Label
@export var hint_label: Label

var _revealed := 0
var _opened := false
var _done := false


func _ready() -> void:
	if solution == null:
		push_warning("SealedSolution : aucune ressource SolutionData assignée.")
		solution = SolutionData.new()
	if title_label:
		title_label.text = solution.title
	if seal_button:
		seal_button.text = "Briser le sceau"
		seal_button.tooltip_text = solution.seal_text
		seal_button.pressed.connect(break_seal)
		seal_button.visible = require_seal_break
		seal_button.grab_focus()
	if content:
		content.visible = false
	if entries_label:
		entries_label.text = ""
	if quote_label:
		quote_label.visible = false
	_set_hint("Briser le sceau pour lire la solution." if require_seal_break else "")
	if not require_seal_break:
		break_seal()


func _unhandled_input(event: InputEvent) -> void:
	var advance := event.is_action_pressed("interact") or event.is_action_pressed("ui_accept")
	if event is InputEventMouseButton and event.is_pressed() and (event as InputEventMouseButton).button_index == MOUSE_BUTTON_LEFT:
		advance = true
	if not advance:
		return
	if not _opened:
		break_seal()  # la touche « interact » vaut un clic sur le sceau
		get_viewport().set_input_as_handled()
		return
	if _done:
		closed.emit()
	elif not auto_reveal:
		reveal_next()
	get_viewport().set_input_as_handled()


## Appelé par le contrôleur de flux avec l'état de la salle, pour le récapitulatif.
func present(collected: Array[StringName], total: int) -> void:
	if recap_label:
		recap_label.text = "Preuves réunies : %d sur %d" % [collected.size(), total]
		recap_label.visible = total > 0


func break_seal() -> void:
	if _opened:
		return
	_opened = true
	if seal_button:
		seal_button.visible = false
	if content:
		content.visible = true
	if verdict_label:
		verdict_label.text = solution.verdict
	seal_broken.emit()
	if solution.entries.is_empty():
		_finish()
	elif auto_reveal:
		_auto_reveal()
	else:
		_set_hint("E · ligne suivante")


## Révèle la prochaine ligne de la chronologie.
func reveal_next() -> void:
	if _done or _revealed >= solution.entries.size():
		return
	if entries_label:
		if _revealed > 0:
			entries_label.append_text("\n")
		entries_label.append_text(solution.entries[_revealed])
	_revealed += 1
	if _revealed >= solution.entries.size():
		_finish()


func _auto_reveal() -> void:
	while _revealed < solution.entries.size():
		reveal_next()
		if auto_reveal_interval > 0.0 and _revealed < solution.entries.size():
			await get_tree().create_timer(auto_reveal_interval).timeout


func _finish() -> void:
	_done = true
	if quote_label and solution.closing_quote != "":
		var author := (" — %s" % solution.quote_author) if solution.quote_author != "" else ""
		quote_label.text = "« %s »%s" % [solution.closing_quote, author]
		quote_label.visible = true
	_set_hint("Dossier clos. E · recommencer")
	fully_revealed.emit()


func _set_hint(text: String) -> void:
	if hint_label:
		hint_label.text = text
		hint_label.visible = text != ""
