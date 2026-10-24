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
##       ├── SaveInfo (Label)    -- « 3 preuves sur 8 · 2026-10-24 14:02 »
##       ├── StartButton (Button)   -- « Ouvrir le dossier » ou « Reprendre l'enquête »
##       ├── NewGameButton (Button) -- visible seulement avec une sauvegarde
##       ├── SettingsButton (Button)
##       ├── QuitButton (Button) -- masqué automatiquement sur le web
##       └── Hint (Label)

## Émis quand le joueur lance ou reprend l'enquête (Main décide selon la sauvegarde).
signal start_requested
## Émis quand le joueur veut repartir de zéro ; Main efface la sauvegarde.
signal new_game_requested
## Émis quand le joueur ouvre les paramètres.
signal settings_requested
## Émis quand le joueur veut quitter le jeu.
signal quit_requested

@export var unit_text: String = "Section des crimes majeurs"
@export var title_text: String = "Dossier 25-10-4471 — Caron, Julien"
@export_multiline var subtitle_text: String = "Le sgt-dét. Lavoie a demandé un deuxième avis.\nLa scène est encore telle qu'on l'a trouvée."
@export var start_label: String = "Ouvrir le dossier"
@export var continue_label: String = "Reprendre l'enquête"
@export var new_game_label: String = "Nouvelle enquête"
@export var settings_label: String = "Paramètres"
@export var quit_label: String = "Quitter"
## Si vrai, la touche « interact » / ui_accept lance aussi l'enquête.
@export var start_on_interact: bool = true

@export_group("UI")
@export var unit_label: Label
@export var title_label: Label
@export var subtitle_label: Label
@export var save_info_label: Label
@export var start_button: Button
@export var new_game_button: Button
@export var settings_button: Button
@export var quit_button: Button
@export var hint_label: Label

var _started := false
var _has_save := false


func _ready() -> void:
	if unit_label:
		unit_label.text = unit_text
	if title_label:
		title_label.text = title_text
	if subtitle_label:
		subtitle_label.text = subtitle_text
	if start_button:
		start_button.pressed.connect(request_start)
		start_button.grab_focus()
	if new_game_button:
		new_game_button.text = new_game_label
		new_game_button.pressed.connect(request_new_game)
	_refresh_save_ui()
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


## Appelé par Main : adapte les boutons à la présence d'une sauvegarde.
func set_save_info(has_save: bool, summary: String = "") -> void:
	_has_save = has_save
	if save_info_label:
		save_info_label.text = summary
		save_info_label.visible = has_save and summary != ""
	_refresh_save_ui()


func _refresh_save_ui() -> void:
	if start_button:
		start_button.text = continue_label if _has_save else start_label
	if new_game_button:
		new_game_button.visible = _has_save
	if save_info_label and not _has_save:
		save_info_label.visible = false


## Lance l'enquête (une seule fois, même si on appuie deux fois pendant le fondu).
func request_start() -> void:
	if _started:
		return
	_started = true
	_set_buttons_enabled(false)
	start_requested.emit()


func request_new_game() -> void:
	if _started:
		return
	_started = true
	_set_buttons_enabled(false)
	new_game_requested.emit()


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
	if new_game_button:
		new_game_button.disabled = not enabled
	if settings_button:
		settings_button.disabled = not enabled
	if quit_button:
		quit_button.disabled = not enabled
