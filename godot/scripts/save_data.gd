class_name SaveData
extends RefCounted
## État persistant d'une partie. Purement des données, sérialisées en JSON par SaveStore.
##
## On passe par un Dictionary plutôt que par ResourceSaver : charger une Resource depuis
## user:// peut exécuter du script embarqué, un JSON non.

## Incrémenter quand le format change ; from_dict() peut alors migrer.
const FORMAT_VERSION := 1

## Pièces à conviction collectées, dans l'ordre.
var collected_evidence: Array[StringName] = []
## Zones one_shot déjà déclenchées (la sortie n'y est jamais, pour pouvoir ressortir).
var fired_triggers: Array[StringName] = []
## Dernière position connue du joueur dans la salle.
var player_position: Vector2 = Vector2.ZERO
var has_player_position: bool = false
## Vrai une fois la solution scellée atteinte.
var case_closed: bool = false
## Horodatage de la dernière écriture (Time.get_datetime_string_from_system()).
var saved_at: String = ""


## Vrai si rien n'a encore été fait (équivaut à « pas de sauvegarde »).
func is_empty() -> bool:
	return collected_evidence.is_empty() and fired_triggers.is_empty() \
		and not has_player_position and not case_closed


func to_dict() -> Dictionary:
	var evidence: Array = []
	for id in collected_evidence:
		evidence.append(String(id))
	var triggers: Array = []
	for id in fired_triggers:
		triggers.append(String(id))
	return {
		"version": FORMAT_VERSION,
		"collected_evidence": evidence,
		"fired_triggers": triggers,
		"player_position": {"x": player_position.x, "y": player_position.y},
		"has_player_position": has_player_position,
		"case_closed": case_closed,
		"saved_at": saved_at,
	}


static func from_dict(dict: Dictionary) -> SaveData:
	var data := SaveData.new()
	var version := int(dict.get("version", 0))
	if version > FORMAT_VERSION:
		push_warning("SaveData : version %d plus récente que %d, lecture au mieux." % [version, FORMAT_VERSION])
	for raw in dict.get("collected_evidence", []):
		data.collected_evidence.append(StringName(String(raw)))
	for raw in dict.get("fired_triggers", []):
		data.fired_triggers.append(StringName(String(raw)))
	var pos: Variant = dict.get("player_position", null)
	if pos is Dictionary:
		data.player_position = Vector2(float(pos.get("x", 0.0)), float(pos.get("y", 0.0)))
	data.has_player_position = bool(dict.get("has_player_position", false))
	data.case_closed = bool(dict.get("case_closed", false))
	data.saved_at = String(dict.get("saved_at", ""))
	return data
