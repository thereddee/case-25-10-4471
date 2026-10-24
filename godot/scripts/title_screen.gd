class_name TitleScreen
extends Control
## Écran titre. Ne connaît ni la salle ni la solution : il émet des signaux, Main enchaîne.
## Structure attendue :
##   TitleScreen (Control)
##   ├── Background (ColorRect)
##   └── Center › Panel › Margin › VBox
##       ├── Unit (Label)        -- « Section des crimes majeurs »
##       ├── Title (Label)       -- « Dossier 25-10-4471 — Caron, Julien »
##       ├── Subtitle (Label)
##       ├── StartButton (Button)
##       ├── SettingsButton (Button)
##       ├── QuitButton (Button) -- masqué automatiquement sur le web
##       └── Hint (Label)

## Émis quand le joueur lance l'enquête.
signal start_requested
## Émis quand le joueur ouvre les paramètres.
signal settings_requested
## Émis quand le joueur veut quitter le jeu.
signal quit_requested

@export var unit_text: String = "Section des crimes majeurs"
@export var title_text: String = "Dossier 25-10-4471 — Caron, Julien"
@export_multiline var subtitle_text: String = "Le sgt-dét. Lavoie a demandé un deuxième avis.\nLa scène est encore telle qu'on l'a trouvée."
@export var start_label: String = "Ouvrir le dossier"
@export var settings_label: String = "Paramètres"
@export var quit_label: String = "Quitter"
## Si vrai, la touche « interact » / ui_accept lance aussi l'enquête.
@export var start_on_interact: bool = true

@export_group("UI")
@export var unit_label: Label
@export var title_label: Label
@export var subtitle_label: Label
@export var start_button: Button
@export var settings_button: Button
@export var quit_button: Button
@export var hint_label: Label

var _started := false


func _ready() -> void:
	if unit_label:
		unit_label.text = unit_text
	if title_label:
		title_label.text = title_text
	if subtitle_label:
		subtitle_label.text = subtitle_text
	if start_button:
		start_button.text = start_label
		start_button.pressed.connect(request_start)
		start_button.grab_focus()
	if settings_button:
		settings_button.text = settings_label
		settings_button.pressed.connect(request_settings)
	if quit_button:
		quit_button.text = quit_label
		quit_button.pressed.connect(request_quit)
		# Quitter n'a pas de sens dans un navigateur.
		quit_button.visible = not OS.has_feature("web")
	if hint_label:
		hint_label.text = "E · ouvrir le dossier" if start_on_interact else ""
		hint_label.visible = hint_label.text != ""


func _unhandled_input(event: InputEvent) -> void:
	if not start_on_interact:
		return
	if event.is_action_pressed("interact") or event.is_action_pressed("ui_accept"):
		request_start()
		get_viewport().set_input_as_handled()


## Lance l'enquête (une seule fois, même si on appuie deux fois pendant le fondu).
func request_start() -> void:
	if _started:
		return
	_started = true
	_set_buttons_enabled(false)
	start_requested.emit()


func request_settings() -> void:
	settings_requested.emit()


func request_quit() -> void:
	quit_requested.emit()


## Redonne le focus au bouton principal (après la fermeture des paramètres).
func focus_default() -> void:
	if start_button:
		start_button.grab_focus()


func _set_buttons_enabled(enabled: bool) -> void:
	if start_button:
		start_button.disabled = not enabled
	if settings_button:
		settings_button.disabled = not enabled
	if quit_button:
		quit_button.disabled = not enabled
