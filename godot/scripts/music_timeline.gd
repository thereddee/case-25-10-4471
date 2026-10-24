class_name MusicTimeline
extends Resource
## La liste de lecture « maison » de Julien. Règle de la maison : elle n'arrête jamais.
##
## L'heure du décès se déduit du point de pause sur le téléphone :
## heure de départ + durée des pistes jouées au complet + décalage dans la piste en pause.
## Tout est exposé dans l'inspecteur pour pouvoir changer l'énigme sans toucher au code.

## Heure (HH:MM, 24 h) à laquelle la musique a démarré.
@export var start_time: String = "19:40"

## Durée de chaque piste, en secondes, dans l'ordre de la liste de lecture.
@export var track_durations_seconds: PackedInt32Array = PackedInt32Array()

## Index (base 0) de la piste affichée en pause sur le téléphone. 37 = piste 38.
@export_range(0, 999) var paused_track_index: int = 37

## Position dans la piste en pause, en secondes. 107 = 1:47.
@export_range(0, 36000) var paused_offset_seconds: int = 107


## Nombre de pistes jouées au complet avant la pause.
func completed_track_count() -> int:
	return mini(paused_track_index, track_durations_seconds.size())


## Secondes de musique écoulées entre le départ et la pause.
func elapsed_seconds() -> int:
	var total := 0
	for i in completed_track_count():
		total += track_durations_seconds[i]
	return total + paused_offset_seconds


## Minutes écoulées, arrondies au plus proche (145 avec les valeurs par défaut).
func elapsed_minutes() -> int:
	return roundi(elapsed_seconds() / 60.0)


## Heure de la pause au format HH:MM (22:05 avec les valeurs par défaut).
func pause_time() -> String:
	var seconds := _parse_hhmm(start_time) + elapsed_seconds()
	return _format_hhmm(seconds)


## Numéro de piste tel qu'affiché à l'écran (base 1).
func paused_track_number() -> int:
	return paused_track_index + 1


## Décalage dans la piste en pause, au format M:SS.
func paused_offset_label() -> String:
	return "%d:%02d" % [int(paused_offset_seconds / 60.0), paused_offset_seconds % 60]


static func _parse_hhmm(text: String) -> int:
	var parts := text.split(":")
	if parts.size() != 2:
		push_warning("MusicTimeline: heure invalide « %s », attendu HH:MM" % text)
		return 0
	return int(parts[0]) * 3600 + int(parts[1]) * 60


static func _format_hhmm(total_seconds: int) -> String:
	var t := posmod(total_seconds, 86400)
	var hours := int(t / 3600.0)
	var minutes := int((t % 3600) / 60.0)
	return "%02d:%02d" % [hours, minutes]
