class_name AudioSettings
extends RefCounted
## Volumes des bus audio, persistés dans user://settings.cfg.
##
## Aucune dépendance à l'UI : le menu Paramètres s'en sert, Main l'applique au démarrage.
## Les volumes sont stockés en linéaire (0.0 à 1.0) et convertis en dB à l'application.

const SAVE_PATH := "user://settings.cfg"
const SECTION := "audio"
## Bus pilotés, dans l'ordre d'affichage. Doivent exister dans default_bus_layout.tres.
const BUSES: Array[StringName] = [&"Master", &"Music", &"SFX"]
const DEFAULT_VOLUME := 1.0
## Sous ce seuil linéaire, le bus est coupé plutôt que mis à -80 dB.
const MUTE_THRESHOLD := 0.001

## bus (StringName) -> volume linéaire (float).
var volumes: Dictionary = {}


func _init() -> void:
	for bus in BUSES:
		volumes[bus] = DEFAULT_VOLUME


## Charge le fichier s'il existe ; sinon retourne les valeurs par défaut.
static func load_or_default() -> AudioSettings:
	var settings := AudioSettings.new()
	var config := ConfigFile.new()
	if config.load(SAVE_PATH) != OK:
		return settings
	for bus in BUSES:
		settings.volumes[bus] = clampf(float(config.get_value(SECTION, String(bus), DEFAULT_VOLUME)), 0.0, 1.0)
	return settings


## Écrit le fichier. Retourne le code d'erreur de ConfigFile.save().
func save() -> Error:
	var config := ConfigFile.new()
	config.load(SAVE_PATH)  # garde les autres sections si le fichier existe déjà
	for bus in BUSES:
		config.set_value(SECTION, String(bus), get_volume(bus))
	var err := config.save(SAVE_PATH)
	if err != OK:
		push_warning("AudioSettings : impossible d'écrire %s (erreur %d)." % [SAVE_PATH, err])
	return err


## Pousse tous les volumes vers AudioServer.
func apply() -> void:
	for bus in BUSES:
		apply_bus(bus)


## Pousse un seul bus vers AudioServer.
func apply_bus(bus: StringName) -> void:
	var index := AudioServer.get_bus_index(String(bus))
	if index < 0:
		push_warning("AudioSettings : bus « %s » introuvable dans la disposition audio." % bus)
		return
	var linear := get_volume(bus)
	AudioServer.set_bus_mute(index, linear < MUTE_THRESHOLD)
	AudioServer.set_bus_volume_db(index, linear_to_db(maxf(linear, MUTE_THRESHOLD)))


func get_volume(bus: StringName) -> float:
	return float(volumes.get(bus, DEFAULT_VOLUME))


## Fixe et applique immédiatement (ne sauvegarde pas : appeler save()).
func set_volume(bus: StringName, linear: float) -> void:
	volumes[bus] = clampf(linear, 0.0, 1.0)
	apply_bus(bus)
