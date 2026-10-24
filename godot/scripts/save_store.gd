class_name SaveStore
extends RefCounted
## Lecture/écriture de SaveData en JSON dans user://. Statique, sans état, sans UI.

const DEFAULT_PATH := "user://save.json"


## Chemin d'un emplacement nommé : user://<slot>.json.
static func path_for_slot(slot: String) -> String:
	return "user://%s.json" % slot if slot != "" else DEFAULT_PATH


static func exists(path: String = DEFAULT_PATH) -> bool:
	return FileAccess.file_exists(path)


## Charge le fichier ; retourne une SaveData vide s'il manque ou est illisible.
static func load_or_default(path: String = DEFAULT_PATH) -> SaveData:
	if not FileAccess.file_exists(path):
		return SaveData.new()
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		push_warning("SaveStore : impossible d'ouvrir %s (erreur %d)." % [path, FileAccess.get_open_error()])
		return SaveData.new()
	var parsed: Variant = JSON.parse_string(file.get_as_text())
	if not (parsed is Dictionary):
		push_warning("SaveStore : %s n'est pas un JSON valide, sauvegarde ignorée." % path)
		return SaveData.new()
	return SaveData.from_dict(parsed)


## Écrit le fichier. Retourne le code d'erreur.
static func save(data: SaveData, path: String = DEFAULT_PATH) -> Error:
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		var err := FileAccess.get_open_error()
		push_warning("SaveStore : impossible d'écrire %s (erreur %d)." % [path, err])
		return err
	file.store_string(JSON.stringify(data.to_dict(), "\t"))
	file.close()
	return OK


## Supprime la sauvegarde. OK si elle n'existait pas.
static func clear(path: String = DEFAULT_PATH) -> Error:
	if not FileAccess.file_exists(path):
		return OK
	return DirAccess.remove_absolute(ProjectSettings.globalize_path(path))
