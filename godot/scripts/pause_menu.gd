class_name PauseMenu
extends CanvasLayer
## Menu pause. Met l'arbre en pause et propose Reprendre / Retour au titre.
##
## Possédé par Main (il survit aux changements de scène) et activé seulement quand une scène
## jouable est affichée. Tourne en PROCESS_MODE_ALWAYS pour recevoir l'input pendant la pause.
## Il ne change jamais de scène lui-même : il émet des signaux, Main enchaîne. Structure :
##   PauseMenu (CanvasLayer, layer 50)
##   └── Root (Control, plein écran)
##       ├── Dim (ColorRect)              -- assombrit le jeu
##       └── Center › Panel › Margin › VBox
##           ├── Title (Label)
##           ├── ResumeButton (Button)
##           ├── TitleButton (Button)
##           └── Hint (Label)

## Émis quand le jeu passe en pause.
signal paused
## Émis quand le jeu reprend.
signal resumed
## Émis quand le joueur demande le retour à l'écran titre (le jeu est déjà dépausé).
signal return_to_title_requested

## Faux = la touche pause est ignorée (écran titre, solution, fondu en cours).
@export var enabled: bool = false:
	set(value):
		enabled = value
		# Le setter tourne aussi au chargement du .tscn, avant l'entrée dans l'arbre.
		if is_inside_tree() and not enabled and is_paused():
			resume()

@export var title_text: String = "Pause"
@export var resume_label: String = "Reprendre"
@export var title_label_text: String = "Retour au titre"

@export_group("UI")
@export var root: Control
@export var title_label: Label
@export var resume_button: Button
@export var title_button: Button
@export var hint_label: Label


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	if root:
		root.visible = false
	if title_label:
		title_label.text = title_text
	if resume_button:
		resume_button.text = resume_label
		resume_button.pressed.connect(resume)
	if title_button:
		title_button.text = title_label_text
		title_button.pressed.connect(request_return_to_title)
	if hint_label:
		hint_label.text = "Échap · reprendre"


func _unhandled_input(event: InputEvent) -> void:
	if not event.is_action_pressed("pause"):
		return
	if is_paused():
		resume()
		get_viewport().set_input_as_handled()
	elif enabled:
		pause()
		get_viewport().set_input_as_handled()


func is_paused() -> bool:
	return is_inside_tree() and get_tree().paused


func pause() -> void:
	if is_paused() or not enabled:
		return
	get_tree().paused = true
	if root:
		root.visible = true
	if resume_button:
		resume_button.grab_focus()
	paused.emit()


func resume() -> void:
	if not is_paused():
		return
	get_tree().paused = false
	if root:
		root.visible = false
	resumed.emit()


## Dépause d'abord, pour que le fondu de Main puisse tourner, puis signale la demande.
func request_return_to_title() -> void:
	resume()
	return_to_title_requested.emit()
