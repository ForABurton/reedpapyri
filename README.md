# ReedPapyri — Papyrus Documentation & Wiki Toolchain

ReedPapyri is a powerful Python toolchain for generating wikis and managing documentation for Papyrus scripts used in Bethesda games and mods. 

[![Status: Experimental](https://img.shields.io/badge/status-experimental-orange.svg)](https://github.com/)
[![Type: Personal Project](https://img.shields.io/badge/type-personal-blueviolet.svg)](https://github.com/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/)

## Overview
ReedPapyri is especially useful for Starfield, which has for several years lacked a comprehensive community scripting reference wiki, but it can be used with other Bethesda games (e.g. Fallout 4) as well. ReedPapyri helps modders create their own detailed documentation for Starfield's scripting systems and potentially even host separate knowledge bases for large mods. This way if you prefer having a Skyrim or Fallout 4 style Starfield wiki you can build your own from the script sources you have installed with the game (e.g. ls /mysteaminstalldirectory/steamapps/common/Starfield/Data/scripts/source), and if you're a modder with your own scripting armamentaria you can see them documented in all of the glory of the standard Papyrus library scripting primitives you used to build them (which is a reminder that in Papyrus you are really making new types, not just scripts!). This tool is Linux focused, in some celebration of the fact that Proton's kernel32 support has extended to things like CopyFile2 so that we don't necessarily need weird shim or IAT shenanigans to use much of the Creation Kit anymore.

* Multiple Export Modes: Generate documentation in MediaWiki (.wiki), SQL databases, ZIP archives, or MediaWiki XML dumps.
* Auto-linking and auto-indexing documentation like the unavailable official Papyrus Wikis for Fallout 4 and Skyrim.
* Basic Docker Compose generation (sqlite backend)

### Experimental Features

* Decompilation (invocation) support: The ability to decompile .pex files into .psc is experimental and might not work for all cases.
* Custom Knowledge Bases for Mods: Generate separate knowledge bases for large mods.
* Pygments Syntax Highlighting: Experimental for MediaWiki's SyntaxHighlight_GeSHi extension, with full integration still being developed.

## Installation

Clone the repository:

```
git clone https://github.com/your-username/ReedPapyri.git
cd ReedPapyri
```
> remember it's best to make a clean working directory

Install dependencies:
pyyaml, sqlite3, pygments (optional), docker (optional), pyparsing (optional/experimental), psycopg2 (optional)

Ensure Docker is installed if using the Docker setup.

(Optional) Set up a Papyrus decompiler, like Champollion if you wish to decompile .pex files.

## Usage


### Example 1: Export to SQL Database

This example stores documentation in a SQL database (sqlite), including an auto-generated index.
This is the place to start for enabling fun programmatic analyses or web visualizations.

```
python3 reedpapyri.py . ./StarDocBase --index --mode sql --db-conn ./StarDocBase/lightspeed.db --db-dialect sqlite
```

Output:
```
🔧 ReedPapyri — Papyrus Documentation & Wiki Toolchain
📂 Scanning directory: .
📄 Parsing Actor.psc
✅ Stored Actor in SQL database
📄 Parsing ObjectReference.psc
✅ Stored ObjectReference in SQL database
✅ Added index page → Category:Papyrus (via SQLDocSink)
💾 Saved SQL database → ./StarDocBase/lightspeed.db
✅ Completed: 2 Papyrus scripts processed in mode 'sql'.
🎆 Done.
```
### Example 2: Export to MediaWiki XML Format

Generate a MediaWiki XML dump for importing into a MediaWiki instance, using Docker for the setup.
This is the native format used by MediaWiki software when you export or import multiple pages at once, ideal for Special: pages wiki clickops.

```
python3 reedpapyri.py . ./StarDocBase --index --mode xml
```

### Example 3: Export to ZIP Archive

Create a ZIP archive of .wiki files. This mode is useful for distributing documentation or merging it or searching through it (e.g. with rg) in your terminal.

```
python3 reedpapyri.py . ./StarDocBase --index --mode zip
```


### Example 4: Generate MediaWiki Wiki Files

Generate MediaWiki .wiki files, including a sidebar and an index page.
These are the individual page files, best for copying into Wiki source editors on ones you are a member of, or AI analyses.

```
python3 reedpapyri.py . ./StarDocBase --index --mode wiki
```

## Command-Line Switches

Below is a table describing all available command-line switches for **ReedPapyri**.

| Switch | Description |
|--------|-------------|
| `-h`, `--help` | Show help message and exit |
| `--mode {wiki,sql,zip,xml}` | Output mode: choose between `wiki`, `sql`, `zip`, or `xml` |
| `--db-conn DB_CONN` | SQL connection string or path (required if `mode=sql`) |
| `--db-dialect {sqlite,postgres}` | Database dialect for SQL mode (`sqlite` or `postgres`) |
| `--index` | Generate index (`Category:Papyrus`) after docs |
| `--user-types USER_TYPES` | Path to JSON file of user-defined types for linking |
| `--project-name PROJECT_NAME` | Project name for index or Docker setup |
| `--docker` | Generate `docker-compose.yml` for hosting docs |
| `--ssl` | Enable HTTPS with Caddy |
| `--domain DOMAIN` | Domain for HTTPS setup (required if `--ssl` is used) |
| `--email EMAIL` | Email for Let's Encrypt SSL |
| `--local-ssl` | Use local/internal certificates |
| `--db` | Include database container in `docker-compose` |
| `--no-docgen` | Skip `docgen` container in Docker setup |
| `--build-docgen` | Build `docgen` from `Dockerfile.docgen` |
| `--wiki-user WIKI_USER` | Contributor username for XML exports |
| `--wiki-base WIKI_BASE` | Base URL for the MediaWiki site in XML exports |
| `--install-syntax-highlighting` | Attempt to build and install Papyrus syntax highlighting in MediaWiki SyntaxHighlight_GeSHi (this happens outside the container in `./extensions`) |
| `--no-marker` | Do not include invisible generation markers in wiki output |
| `--no-marker-seconds` | Truncate generation marker timestamps to minutes (less noisy diffs) |
| `--syntax-language SYNTAX_LANGUAGE` | Specify the language for syntax highlighting (e.g., `papyrus`, `AutoIt`, `pascal`) |
| `--preproc-foreign-decompiler` | Enable preprocessing step to decompile `.pex` files before docgen |
| `--foreign-decompiler-path FOREIGN_DECOMPILER_PATH` | Path to the external decompiler executable (EXE or native binary) |
| `--foreign-decompiler-runner FOREIGN_DECOMPILER_RUNNER` | Optional execution wrapper for non-Windows environments (e.g., `wine`, `proton run`, `bottles-cli run`) |
| `--foreign-decompiler-force-decompile` | Force re-decompilation even if the existing `.psc` is newer than the `.pex` |
| `--foreign-decompiler-env [FOREIGN_DECOMPILER_ENV [FOREIGN_DECOMPILER_ENV ...]]` | Extra environment variables for the decompiler (e.g., `WINEPREFIX=~/.wine`, `WINEDEBUG=-all`) |
| `--parser {regular,pyparsing}` | Select the parser to use: `regular` (default) or `pyparsing` |


## Docker (docker-compose) generation

ReedPapyri can generate a Docker environment for hosting the documentation using MediaWiki, Caddy, and Pygmentize for syntax highlighting. Note: Docker mode always uses XML export mode, even if other modes like wiki or zip are specified.

To Generate Docker Setup:
```
$python3 script.py ./Scripts ./Output --mode xml --docker --wiki-user mrcontributor --wiki-base papyrus_wiki
```
To Start the Docker Containers:
docker-compose up

After the containers are up, access MediaWiki at http://localhost:2450.

### Notes

Decompilation support is experimental and may not work for all .pex files. Enable it with --preproc-foreign-decompiler.
Pygments Syntax Highlighting code is experimental for MediaWiki's SyntaxHighlight_GeSHi extension. Manual installation and configuration may be required, emitting from the CLI isn't enabled.

For best results, work in a clean directory. Place .psc files in a fresh directory as ReedPapyri can generate many .wiki files, and Docker-related artifacts like docker-compose.yml will be created as well.

## Docker MediaWiki Setup Hints 
(currently this is scaled back to generating a sqlite setup in a docker-compose volume vs autoconfiguring the wiki programmatically or using postgres)

Generate the Docker Environment:
After running ReedPapyri with --docker and generating the docker-compose.yml file, you can bring up the containers by running:

```
docker-compose up
```

This will set up and start the MediaWiki container along with other necessary services, such as in an anticipated enhancement, with --ssl, Caddy (for reverse proxy and SSL).

Complete the Interactive MediaWiki Installer:
After running the command, MediaWiki will be accessible on port 2450 (mapped to 80 inside the container). Open a web browser and navigate to:

http://localhost:2450

This will take you to the MediaWiki installer interface.

Install the SyntaxHighlight_GeSHi Extension:
To enable syntax highlighting (for Papyrus scripts), you need to install the mediawiki-extensions-SyntaxHighlight_GeSHi extension or a similar one that supports Pygments. This is required if you want to display code snippets with syntax highlighting. If the extension is not already included, follow the installation instructions on MediaWiki’s SyntaxHighlight_GeSHi page, but keeping in mind you must docker exec and docker cp your way around the container volume's layer on the container filesystem.

Download and Back Up LocalSettings.php:
After completing the installer, MediaWiki will provide you with a LocalSettings.php file. This file is crucial for the configuration of your MediaWiki instance. Make sure to download it and back it up immediately. With those out of sync, it is much easier just to reinstall and import.

Maintain Consistency with LocalSettings.php:
MediaWiki is very sensitive to changes in the LocalSettings.php file. It's important that the Docker volume (in this case, mediawiki_papyrus) is kept in sync with the version of LocalSettings.php that you generated during the installer process.

Copy LocalSettings.php to the Docker Container:
From your host machine, copy the LocalSettings.php file into the running MediaWiki container. This file is necessary for proper operation and configuration of your MediaWiki instance:
```
$docker cp LocalSettings.php mediawiki_papyrus:/var/www/html/LocalSettings.php
```
Log In to MediaWiki:
After copying LocalSettings.php, you can now access the MediaWiki instance again in your browser. Log in with the admin credentials you provided during setup (default is admin / adminpass).

Copy Extensions and XML Files:
If you need to install the SyntaxHighlight_GeSHi extension (or you can use AutoIt highlighting ;) ) or other resources, copy them to the appropriate directory inside the container:
```
$docker cp ./extensions/SyntaxHighlight_GeSHi mediawiki_papyrus:/var/www/html/extensions/
$docker cp /path/to/your/PapyrusDocs.xml mediawiki_papyrus:/var/www/html/
```
Import the XML Dump:
Once your .xml dump (generated by ReedPapyri) is copied into the container, you can import it into MediaWiki using the following command:
```
$docker exec -it mediawiki_papyrus bash
>>php /var/www/html/maintenance/importDump.php /var/www/html/file.xml
```
Or, much more reliably (but a whole game's worth of files may challenge the php upload form and appear not to populate the wiki):
To import additional Wiki files, navigate to:
http://localhost:8081/index.php/Special:Import

Verify Installation:

To check the installed extensions, go to:
http://localhost:2450/index.php/Special:Version
(You must be logged in as an admin to import files.)

Custom Namespaces:
You can import different Papyrus mod projects and mods into custom namespaces. This allows you to organize documentation for multiple mods in a way that they can coexist in the same MediaWiki instance. Learn more about custom namespaces at MediaWiki's manual page about namespaces.

With the correct juggling of LocalSettings.php and the database state in your docker volumes, it is even possible to bake your own images for other people to pull off of Docker Hub or GHCI, such that they could have a Starfield Papyrus Wiki or a MajorMod Papyrus Wiki.
