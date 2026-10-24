class_name SettingsMenu
extends CanvasLayer
## Menu Paramètres : un slider par bus audio. Possédé par Main, ouvert depuis le titre ou la pause.
##
## Tourne en PROCESS_MODE_ALWAYS pour fonctionner pendant la pause. Applique les volumes en
## direct et sauvegarde à la fermeture. Tant qu'il est ouvert, il avale l'input non géré pour
## que l'écran dessous (titre, pause) ne réagisse pas. Structure :
##   SettingsMenu (CanvasLayer, layer 60)
##   └── Root (Control, plein écran, caché)
##       ├── Dim (ColorRect)
##       └── Center › Panel › Margin › VBox
##           ├── Title (Label)
##           ├── MasterRow / MusicRow / SfxRow (HBoxContainer)
##           │   ├── Name (Label), Slider (HSlider), Value (Label)
##           ├── BackButton (Button)
##           └── Hint (Label)

## Émis à l'ouverture.
signal opened
## Émis à la fermeture, après sauvegarde.
signal closed
## Émis à chaque changement de slider (bus, volume linéaire).
signal volume_changed(bus: StringName, linear: float)

@export var title_text: String = "Paramètres"
@export var back_label: String = "Retour"
## Joue ce son à chaque relâchement du slider Effets, pour entendre le niveau (vide = rien).
@export var sfx_preview: AudioStream

@export_group("UI")
@export var root: Control
@export var title_label: Label
@export var master_slider: HSlider
@export var master_value: Label
@export var music_slider: HSlider
@export var music_value: Label
@export var sfx_slider: HSlider
@export var sfx_value: Label
@export var back_button: Button
@export var hint_label: Label
@export var preview_player: AudioStreamPlayer

var _settings: AudioSettings
var _open := false
## bus -> { "slider": HSlider, "value": Label }
var _rows: Dictionary = {}


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	_settings = AudioSettings.load_or_default()
	_settings.apply()
	_rows = {
		&"Master": {"slider": master_slider, "value": master_value},
		&"Music": {"slider": music_slider, "value": music_value},
		&"SFX": {"slider": sfx_slider, "value": sfx_value},
	}
	for bus in _rows:
		var slider: HSlider = _rows[bus]["slider"]
		if slider == null:
			continue
		slider.min_value = 0.0
		slider.max_value = 1.0
		slider.step = 0.01
		slider.value_changed.connect(_on_slider_changed.bind(bus))
		slider.drag_ended.connect(_on_slider_drag_ended.bind(bus))
	if title_label:
		title_label.text = title_text
	if back_button:
		back_button.text = back_label
		back_button.pressed.connect(close)
	if hint_label:
		hint_label.text = "Échap · retour"
	if preview_player and sfx_preview:
		preview_player.stream = sfx_preview
		preview_player.bus = &"SFX"
	if root:
		root.visible = false
	_refresh_sliders()


func _unhandled_input(event: InputEvent) -> void:
	if not _open:
		return
	if event.is_action_pressed("ui_cancel") or event.is_action_pressed("pause"):
		close()
	# Ouvert, on avale tout : l'écran dessous ne doit pas réagir à E, Échap, etc.
	get_viewport().set_input_as_handled()


func is_open() -> bool:
	return _open


func open() -> void:
	if _open:
		return
	_open = true
	_settings = AudioSettings.load_or_default()
	_refresh_sliders()
	if root:
		root.visible = true
	if master_slider:
		master_slider.grab_focus()
	opened.emit()


func close() -> void:
	if not _open:
		return
	_open = false
	_settings.save()
	if root:
		root.visible = false
	closed.emit()


func _refresh_sliders() -> void:
	for bus in _rows:
		var slider: HSlider = _rows[bus]["slider"]
		if slider:
			slider.set_value_no_signal(_settings.get_volume(bus))
		_refresh_value_label(bus)


func _refresh_value_label(bus: StringName) -> void:
	var label: Label = _rows[bus]["value"]
	if label:
		label.text = "%d %%" % roundi(_settings.get_volume(bus) * 100.0)


func _on_slider_changed(value: float, bus: StringName) -> void:
	_settings.set_volume(bus, value)
	_refresh_value_label(bus)
	volume_changed.emit(bus, value)


func _on_slider_drag_ended(_value_changed: bool, bus: StringName) -> void:
	if bus == &"SFX" and preview_player and preview_player.stream:
		preview_player.play()
