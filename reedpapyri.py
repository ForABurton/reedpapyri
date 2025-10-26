import yaml
from pathlib import Path
from typing import Dict, Any, List
import os
import re
import json
from pathlib import Path
import sqlite3
from typing import Union
import io
import zipfile
import sys
import shutil
import textwrap
import subprocess

import re
from pathlib import Path



OPEN_SYNTAXHIGHLIGHT_EMITSENTINEL = "<syntaxhighlight lang=\"papyrus\">"
CLOSE_SYNTAXHIGHLIGHT_EMITSENTINEL= "</syntaxhighlight>"

def remap_syntaxhighlight(language: str):
    global OPEN_SYNTAXHIGHLIGHT_EMITSENTINEL
    global CLOSE_SYNTAXHIGHLIGHT_EMITSENTINEL
    
    # Handle special inputs: NORMAL and FALLBACK
    if language.upper() == "NORMAL":
        OPEN_SYNTAXHIGHLIGHT_EMITSENTINEL = "<syntaxhighlight lang=\"papyrus\">"
        CLOSE_SYNTAXHIGHLIGHT_EMITSENTINEL = "</syntaxhighlight>"
    elif language.upper() == "FALLBACK":
        OPEN_SYNTAXHIGHLIGHT_EMITSENTINEL = "<syntaxhighlight lang=\"AutoIt\">"
        CLOSE_SYNTAXHIGHLIGHT_EMITSENTINEL = "</syntaxhighlight>"
    else:
        # For any other language, apply its own syntax highlighting
        OPEN_SYNTAXHIGHLIGHT_EMITSENTINEL = f"<syntaxhighlight lang=\"{language.lower()}\">"
        CLOSE_SYNTAXHIGHLIGHT_EMITSENTINEL = "</syntaxhighlight>"

    # Return the updated semiglobally defined tags
    return OPEN_SYNTAXHIGHLIGHT_EMITSENTINEL, CLOSE_SYNTAXHIGHLIGHT_EMITSENTINEL

class PapyrusPygmentsMediawikiInstallationInstaller:
    def __init__(self, syntaxhighlight_path: str):
        self.syntaxhighlight_path = Path(syntaxhighlight_path).resolve()
        self.pygments_path = self.syntaxhighlight_path / "pygments"
        self.plugin_dir = self.pygments_path / "pygments_papyrus"
        self.lexer_php = self.syntaxhighlight_path / "SyntaxHighlight.lexers.php"
        self.entry_points_file = self.plugin_dir / "entry_points.py"

    def check_environment(self):
        """Verify that the given path looks like a MediaWiki SyntaxHighlight_GeSHi directory."""
        if not self.pygments_path.exists():
            raise FileNotFoundError(
                f"Could not find pygments directory under: {self.syntaxhighlight_path}"
            )
        pygmentize = self.pygments_path / "pygmentize"
        if not pygmentize.exists():
            raise FileNotFoundError(
                f"Could not find pygmentize binary in: {self.pygments_path}"
            )
        print(f"[✔] Found MediaWiki SyntaxHighlight_GeSHi at {self.syntaxhighlight_path}")

    def install_plugin_code(self):
        """Copy Papyrus plugin into the MediaWiki pygments directory."""
        os.makedirs(self.plugin_dir, exist_ok=True)
        plugin_code = textwrap.dedent(
            '''
            from pygments.lexer import RegexLexer
            from pygments.token import Text, Name, Keyword, String, Comment, Number, Operator
            from pygments.formatter import Formatter
            from pygments.filter import Filter
            from pygments.style import Style

            class PapyrusLexer(RegexLexer):
                name = "Papyrus"
                aliases = ["papyrus", "psc"]
                filenames = ["*.psc"]
                tokens = {
                    "root": [
                        (r"\\s+", Text),
                        (r";.*$", Comment.Single),
                        (r"(?i)\\b(scriptname|extends|auto|property|function|event|endfunction|endevent|state|endstate)\\b", Keyword),
                        (r"(?i)\\b(true|false|none)\\b", Keyword.Constant),
                        (r'"[^"\\\\]*(?:\\\\.[^"\\\\]*)*"', String),
                        (r"\\b[0-9]+\\b", Number.Integer),
                        (r"[+\\-*/=<>!]+", Operator),
                        (r"\\b[A-Za-z_][A-Za-z0-9_]*\\b", Name),
                    ]
                }

            class PapyrusHTMLFormatter(Formatter):
                def format(self, tokensource, outfile):
                    for ttype, value in tokensource:
                        outfile.write(value)

            class PapyrusSimplifyFilter(Filter):
                def filter(self, lexer, stream):
                    for ttype, value in stream:
                        yield ttype, value.replace("\\t", "<tab>")

            class PapyrusStyle(Style):
                styles = {{
                    Comment: "italic #6a9955",
                    Keyword: "bold #569cd6",
                    Name: "#9cdcfe",
                    String: "#ce9178",
                    Number: "#b5cea8",
                    Operator: "#d4d4d4",
                }}
            '''
        )
        (self.plugin_dir / "__init__.py").write_text(plugin_code, encoding="utf-8")
        print(f"[✔] Installed Papyrus plugin files into {self.plugin_dir}")

    def create_entry_points(self):
        """Create registration script so bundled Pygments detects the Papyrus plugin."""
        entry_code = textwrap.dedent(
            """
            from pygments.lexers import LEXERS
            from pygments.styles import STYLE_MAP
            from pygments.filters import FILTERS
            from . import PapyrusLexer, PapyrusHTMLFormatter, PapyrusSimplifyFilter, PapyrusStyle

            LEXERS['PapyrusLexer'] = (
                'pygments_papyrus', 'Papyrus', ('papyrus', 'psc'),
                ('*.psc',), ('text/x-papyrus',)
            )
            STYLE_MAP['papyrus-style'] = 'pygments_papyrus:PapyrusStyle'
            FILTERS['papyrus-simplify'] = PapyrusSimplifyFilter
            """
        )
        self.entry_points_file.write_text(entry_code, encoding="utf-8")
        print(f"[✔] Created entry_points.py at {self.entry_points_file}")

    def patch_lexers_php(self):
        """Optionally add Papyrus to SyntaxHighlight.lexers.php if missing."""
        if not self.lexer_php.exists():
            print("[⚠] SyntaxHighlight.lexers.php not found; skipping PHP configuration.")
            return

        text = self.lexer_php.read_text(encoding="utf-8")
        if "'papyrus'" in text:
            print("[ℹ] Papyrus already registered in SyntaxHighlight.lexers.php.")
            return

        insertion = "    'papyrus' => 'Papyrus',\\n"
        # crude heuristic: insert before closing bracket
        new_text = text.replace("];", insertion + "];")
        self.lexer_php.write_text(new_text, encoding="utf-8")
        print(f"[✔] Added papyrus lexer entry to SyntaxHighlight.lexers.php")

    def verify_installation(self):
        """Run the bundled pygmentize binary to verify the lexer registration."""
        pygmentize_bin = self.pygments_path / "pygmentize"
        try:
            result = subprocess.run(
                [str(pygmentize_bin), "-L", "lexers"],
                capture_output=True, text=True, check=True
            )
            if "papyrus" in result.stdout.lower():
                print("[✅] Papyrus lexer registered successfully in pygmentize.")
            else:
                print("[❌] Papyrus not found in pygmentize output.")
        except Exception as e:
            print(f"[⚠] Could not verify installation: {e}")

    def build_pygments_files(self, output_to_stdout=False):
        """Build the necessary Pygments files for the Papyrus plugin."""
        # Install plugin code
        self.install_plugin_code()
        # Create entry points for Pygments
        self.create_entry_points()
        
        # Optionally, print the plugin files to stdout or save to the filesystem
        if output_to_stdout:
            plugin_code = (self.plugin_dir / "__init__.py").read_text(encoding="utf-8")
            entry_code = self.entry_points_file.read_text(encoding="utf-8")
            print("Papyrus Pygments Plugin Code:")
            print(plugin_code)
            print("\nPapyrus Entry Points Code:")
            print(entry_code)
        else:
            print(f"[✔] Pygments files have been built and saved to {self.plugin_dir}")
            print(f"[✔] Entry points created at {self.entry_points_file}")

    def run(self):
        self.check_environment()
        self.build_pygments_files()  # Build the necessary files
        self.patch_lexers_php()
        self.verify_installation()



import subprocess
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
import subprocess
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
import textwrap


import subprocess
import os
from pathlib import Path

class PapyrusDockerComposeBasicSQLLiteVersion:
    """
    Generates docker-compose.yml configurations for Papyrus MediaWiki hosting,
    with optional docgen, SSL via Caddy reverse proxy, and automatic
    SyntaxHighlight_GeSHi + Papyrus Pygments installation and CSS generation.
    """

    def __init__(
        self,
        project_name: str = "papyrus_docs",
        scripts_dir: str = "./Scripts",
        output_dir: str = "./Output",
        wiki_port: int = 8081,
        db_enabled: bool = False,
        auto_import: bool = True,
        xml_filename: str = "PapyrusDocs.xml",
        enable_ssl: bool = False,
        domain: Optional[str] = None,
        email: Optional[str] = None,
        local_ssl: bool = False,
        include_docgen: bool = True,
        build_docgen: bool = False,
        docgen_dockerfile: str = "./Dockerfile.docgen",
        install_syntax_highlighting: bool = False,
    ):
        self.project_name = project_name
        self.scripts_dir = Path(scripts_dir)
        self.output_dir = Path(output_dir)
        self.wiki_port = wiki_port
        self.db_enabled = db_enabled
        self.auto_import = auto_import
        self.xml_filename = xml_filename
        self.enable_ssl = enable_ssl
        self.domain = domain
        self.email = email
        self.local_ssl = local_ssl
        self.include_docgen = include_docgen
        self.build_docgen = build_docgen
        self.docgen_dockerfile = Path(docgen_dockerfile)
        self.install_syntax_highlighting = install_syntax_highlighting

    def _mediawiki_service(self) -> Dict[str, Any]:
        """MediaWiki service for hosting Papyrus documentation."""
        import_cmd = ""
        self.auto_import = False # this one doesn't assume a running MediaWiki instance
        if self.auto_import:
            import_cmd = (
                f"php maintenance/importDump.php /var/www/html/imports/{self.xml_filename} && "
                f"php maintenance/rebuildrecentchanges.php && "
            )

        #ext_dir = self._ensure_syntaxhighlight()

        # ─── Construct service ───────────────────────────────────
        return {
            "image": "mediawiki",
            "container_name": "mediawiki_papyrus",
            "restart": "always",
            "ports": [
                "2450:80"
            ],
            "volumes": [
                "mediawiki_papyrus:/var/www/html",  # Persist MediaWiki data
            ],
            "environment": {
                "MEDIAWIKI_DB_TYPE": "sqlite",# if not self.db_enabled else "postgres",
                "MEDIAWIKI_DB_FILE": "/var/www/html/data/wiki.sqlite",# if not self.db_enabled else "",
                "MEDIAWIKI_SITE_NAME": "mediawiki_papyrus",
                "MEDIAWIKI_SITE_LANG": "en",
                "MEDIAWIKI_ADMIN_USER_NOTETAKING_UNUSED": "admin",
                "MEDIAWIKI_ADMIN_PASS_NOTETAKING_UNUSED": "adminpass",
            },
            #"command": f"bash -c \"{import_cmd} apache2-foreground\"",
        }

    def generate(self, output_file: str = "docker-compose.yml"):
        """Generate docker-compose.yml with appended instructions."""
        
        # The instructions to prepend
        instructions = """# version: '3.8'
# sqlite config!!
# Instructions:
# after generating this file: docker-compose up.
# then navigate to the port in your browser (like 2450 of the 2450:80)
# and complete the interactive installer. 
# Make sure to install the mediawiki-extensions-SyntaxHighlight_GeSHi extension (or Extension:SyntaxHighlight, but similar relationship with pygments) should you want code highlighting.

# Make sure to think carefully about how open a wiki you want, and probably choose Vector.
# It will give you a LocalSettings.php file to download.
# Be sure to keep this and back the specific one up.

# It's important to keep your docker volume (here mediawiki_papyrus) with the same state as the LocalSettings.php that generated.
# Mediawiki is extremely inflexible in this regard...

# then from your host system:
# $ docker cp "LocalSettings.php" mediawiki_papyrus:/var/www/html/LocalSettings.php
# and reopen your browser and log in
# <syntaxhighlight lang="python" line> My code here. </syntaxhighlight> on the pages. AutoIt is somewhat similar, and if you use that it's preinstalled

# $ docker cp ./extensions/SyntaxHighlight_GeSHi mediawiki_papyrus:/var/www/html/extensions/

# $ docker cp /path/to/your/PapyrusDocs.xml mediawiki_papyrus:/var/www/html/
# $ docker exec -it mediawiki_papyrus bash
#>> php /var/www/html/maintenance/importDump.php /var/www/html/file.xml

# http://localhost:2450/index.php/Special:Version will give you the installed extensions.
# http://localhost:8081/index.php/Special:Import will allow you to import Wiki files (while logged in as admin)
# You can import different Papyrus mod projects and mods to a custom namespace so they can coexist.
# See: https://www.mediawiki.org/wiki/Manual:Using_custom_namespaces
"""

        # Create docker-compose structure
        compose = {
            #"version": "3.9", #deprecated in docker-compose
            "services": {
                "mediawiki": self._mediawiki_service(),
            },
            "volumes": {
                "mediawiki_papyrus": {},
            }
        }

        # Combine instructions with YAML dump
        with open(output_file, 'w', encoding="utf-8") as file:
            file.write(instructions + "\n\n")
            yaml.dump(compose, file, sort_keys=False)
            
        if self.install_syntax_highlighting:
            print(f"Indicated install syntax highlighting but this simplified version for manual web Mediawiki (vs unattended Postgres, etc.) configuration has you do things manually.")
            print(f"✅ Emitting pygments files (in extensions folder, as ingredient in either form of the syntax highlighting extension.)")
            build_pygments_files(output_to_stdout=True)
            
            installer = PapyrusPygmentsMediawikiInstallationInstaller('./extensions')
            installer.build_pygments_files(output_to_stdout=True)
            
            # formerly, in the complicated flow retired from current consideration, assuming we first git cloned the extension from the correct github version or 
            # https://www.mediawiki.org/wiki/Special:ExtensionDistributor/SyntaxHighlight_GeSHi 
            # installer = PapyrusPygmentsMediawikiInstallationInstaller('./extensions/SyntaxHighlight_GeSHi/pygments')
            #print(f"✅ Installing syntax highlighting extensions.")

        print(f"✅ Generated docker-compose.yml → {output_file}")

    # ───────────────────────────────────────────────
    # HELPER FUNCTIONS FOR USER OPERATIONS
    # ───────────────────────────────────────────────

    def helptheuser_docker_up(self):
        """Run 'docker-compose up' to start the container."""
        print("Running 'docker-compose up'... This may take a while.")
        subprocess.run(["docker-compose", "up"], check=True)

    def helptheuser_docker_cp_localsettings(self, localsettings_path: str):
        """Copy LocalSettings.php into the container."""
        print(f"Copying LocalSettings.php to the container... {localsettings_path}")
        subprocess.run(
            ["docker", "cp", localsettings_path, "mediawiki_papyrus:/var/www/html/LocalSettings.php"],
            check=True,
        )

    def helptheuser_docker_cp_syntaxhighlight_extension(self, syntaxhighlight_path: str):
        """Copy the SyntaxHighlight_GeSHi extension into the container."""
        print(f"Copying SyntaxHighlight_GeSHi extension to the container... {syntaxhighlight_path}")
        subprocess.run(
            ["docker", "cp", syntaxhighlight_path, "mediawiki_papyrus:/var/www/html/extensions/"],
            check=True,
        )

    def helptheuser_docker_cp_xml(self, xml_file_path: str):
        """Copy the XML dump into the container."""
        print(f"Copying XML file to the container... {xml_file_path}")
        subprocess.run(
            ["docker", "cp", xml_file_path, "mediawiki_papyrus:/var/www/html/"],
            check=True,
        )

    def helptheuser_docker_import_xml(self):
        """Import the XML dump into the MediaWiki instance."""
        print("Importing XML dump into the container...")
        subprocess.run(
            [
                "docker", "exec", "-it", "mediawiki_papyrus", "bash", "-c",
                f"php /var/www/html/maintenance/importDump.php /var/www/html/{self.xml_filename}"
            ],
            check=True,
        )

    def helptheuser_browser_access(self):
        """Instruct the user to access the MediaWiki instance in the browser."""
        print(f"Navigate to http://localhost:{self.wiki_port} to complete the MediaWiki installation.")






# e.g. for Starfield (but note that these types do not need to be known...)
KNOWN_TYPES = {
    "TopicInfo": "[[TopicInfo Script]]",
    "Potion": "[[Potion Script]]",
    "Faction": "[[Faction Script]]",
    "Math": "[[Math Script]]",
    "Flora": "[[Flora Script]]",
    "InstanceNamingRules": "[[InstanceNamingRules Script]]",
    "Note": "[[Note Script]]",
    "Game": "[[Game Script]]",
    "PackIn": "[[PackIn Script]]",
    "Class": "[[Class Script]]",
    "Perk": "[[Perk Script]]",
    "IdleMarker": "[[IdleMarker Script]]",
    "Armor": "[[Armor Script]]",
    "Weapon": "[[Weapon Script]]",
    "Container": "[[Container Script]]",
    "Terminal": "[[Terminal Script]]",
    "SpaceshipReference": "[[SpaceshipReference Script]]",
    "InputEnableLayer": "[[InputEnableLayer Script]]",
    "Form": "[[Form Script]]",
    "Actor": "[[Actor Script]]",
    "Static": "[[Static Script]]",
    "MovableStatic": "[[MovableStatic Script]]",
    "ReferenceAlias": "[[ReferenceAlias Script]]",
    "ConditionForm": "[[ConditionForm Script]]",
    "LeveledItem": "[[LeveledItem Script]]",
    "TalkingActivator": "[[TalkingActivator Script]]",
    "Projectile": "[[Projectile Script]]",
    "Race": "[[Race Script]]",
    "Ingredient": "[[Ingredient Script]]",
    "Key": "[[Key Script]]",
    "LocationRefType": "[[LocationRefType Script]]",
    "Curve": "[[Curve Script]]",
    "Scene": "[[Scene Script]]",
    "MagicEffect": "[[MagicEffect Script]]",
    "CameraShot": "[[CameraShot Script]]",
    "SoulGem": "[[SoulGem Script]]",
    "TerminalMenu": "[[TerminalMenu Script]]",
    "AssociationType": "[[AssociationType Script]]",
    "LeveledActor": "[[LeveledActor Script]]",
    "Door": "[[Door Script]]",
    "Message": "[[Message Script]]",
    "GlobalVariable": "[[GlobalVariable Script]]",
    "HeadPart": "[[HeadPart Script]]",
    "SpeechChallengeObject": "[[SpeechChallengeObject Script]]",
    "Alias": "[[Alias Script]]",
    "FormList": "[[FormList Script]]",
    "ObjectReference": "[[ObjectReference Script]]",
    "Book": "[[Book Script]]",
    "WordOfPower": "[[WordOfPower Script]]",
    "Enchantment": "[[Enchantment Script]]",
    "ActiveMagicEffect": "[[ActiveMagicEffect Script]]",
    "Package": "[[Package Script]]",
    "WorldSpace": "[[WorldSpace Script]]",
    "ObjectMod": "[[ObjectMod Script]]",
    "Ammo": "[[Ammo Script]]",
    "ImpactDataSet": "[[ImpactDataSet Script]]",
    "AffinityEvent": "[[AffinityEvent Script]]",
    "LeveledSpaceshipBase": "[[LeveledSpaceshipBase Script]]",
    "Resource": "[[Resource Script]]",
    "Hazard": "[[Hazard Script]]",
    "Weather": "[[Weather Script]]",
    "SpaceshipBase": "[[SpaceshipBase Script]]",
    "Keyword": "[[Keyword Script]]",
    "MiscObject": "[[MiscObject Script]]",
    "VoiceType": "[[VoiceType Script]]",
    "GameplayOption": "[[GameplayOption Script]]",
    "Utility": "[[Utility Script]]",
    "VisualEffect": "[[VisualEffect Script]]",
    "LocationAlias": "[[LocationAlias Script]]",
    "CombatStyle": "[[CombatStyle Script]]",
    "EffectShader": "[[EffectShader Script]]",
    "ConstructibleObject": "[[ConstructibleObject Script]]",
    "ActorBase": "[[ActorBase Script]]",
    "Furniture": "[[Furniture Script]]",
    "LeveledSpell": "[[LeveledSpell Script]]",
    "Location": "[[Location Script]]",
    "Scroll": "[[Scroll Script]]",
    "Activator": "[[Activator Script]]",
    "Cell": "[[Cell Script]]",
    "Quest": "[[Quest Script]]",
    "Planet": "[[Planet Script]]",
    "Shout": "[[Shout Script]]",
    "Action": "[[Action Script]]",
    "ShaderParticleGeometry": "[[ShaderParticleGeometry Script]]",
    "WwiseEvent": "[[WwiseEvent Script]]",
    "ActorValue": "[[ActorValue Script]]",
    "Spell": "[[Spell Script]]",
    "Topic": "[[Topic Script]]",
    "ImageSpaceModifier": "[[ImageSpaceModifier Script]]",
    "RefCollectionAlias": "[[RefCollectionAlias Script]]",
    "Outfit": "[[Outfit Script]]",
    "Light": "[[Light Script]]",
    "MusicType": "[[MusicType Script]]",
    "ResearchProject": "[[ResearchProject Script]]",
    "ScriptObject": "[[ScriptObject Script]]",
    "Idle": "[[Idle Script]]",
    "Explosion": "[[Explosion Script]]"
}


from datetime import datetime

# instrument emitted articles with marker
INCLUDE_GENERATION_MARKER = True
INCLUDE_MARKER_SECONDS = True

def _generation_marker() -> str:
    """Return an invisible MediaWiki marker identifying generator and timestamp."""
    if not INCLUDE_GENERATION_MARKER:
        return ""

    # Choose timestamp precision
    timespec = "seconds" if INCLUDE_MARKER_SECONDS else "minutes"
    ts = datetime.utcnow().isoformat(timespec=timespec)

    return f"<noinclude><!-- Generated by ReedPapyri at {ts} UTC --></noinclude>"


def link_type(t: str) -> str:
    """Link known Papyrus types to wiki pages, including inline text linking."""
    t = t.strip()
    # If it's a known type name, return linked version
    if t in KNOWN_TYPES:
        return KNOWN_TYPES[t]
    # Inline linking for words like 'Faction' inside sentences
    for typename, link in KNOWN_TYPES.items():
        # Match standalone words only (avoid partial matches)
        t = re.sub(rf'\b{typename}\b', f"{link}", t)
    return t


def merge_user_types(user_type_file: Optional[str]):
    if user_type_file and Path(user_type_file).exists():
        with open(user_type_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        for t in data:
            KNOWN_TYPES[t] = f"[[{t} Script]]"






class PapyrusStruct:
    def __init__(self, name: str, members: List[str], description: str = ""):
        self.name = name
        self.members = members
        self.description = description

    def to_mediawiki(self) -> str:
        lines = [f"=== {self.name} ==="]
        if self.description:
            lines.append(self.description)
        #lines.append("<syntaxhighlight lang=\"papyrus\">")
        lines.append(OPEN_SYNTAXHIGHLIGHT_EMITSENTINEL)
        lines.append(f"Struct {self.name}")
        for m in self.members:
            lines.append(f" {m}")
        lines.append("EndStruct")
        #lines.append("</syntaxhighlight>")
        lines.append(CLOSE_SYNTAXHIGHLIGHT_EMITSENTINEL)
        lines.append("")
        for m in self.members:
            lines.append(f"*'''{m}'''")
        return "\n".join(lines)


class PapyrusProperty:
    def __init__(self, name: str, prop_type: str, flags: str = "", description: str = ""):
        self.name = name
        self.prop_type = prop_type
        self.flags = flags
        self.description = description

    def to_mediawiki(self) -> str:
        flag_text = f" [{self.flags}]" if self.flags else ""
        desc = f": {self.description}" if self.description else ""
        return f"*{link_type(self.prop_type)} {self.name}{flag_text}{desc}"


class PapyrusFunction:
    def __init__(
        self,
        name: str,
        return_type: str,
        params: str,
        flags: str = "",
        description: str = "",
        param_docs: Dict[str, str] = None,
    ):
        self.name = name
        self.return_type = return_type
        self.params = params
        self.flags = flags
        self.description = description
        self.param_docs = param_docs or {}
        self.references: set[str] = set()
        self.examples: list[str] = []  # store discovered example lines if found

    # --- New Helper: Generate smarter, style-matched wiki output ---
    def to_mediawiki(self, parent_script: str, siblings: List[str]) -> str:
        desc = self.description.strip()
        if not desc:
            desc = f"Documentation for {self.name}."

        # Automatically link known script types inside description text
        desc = link_type(desc)

        markup = [
            "[[Category:Scripting]]",
            "[[Category:Papyrus]]",
            f"'''Member of:''' [[{parent_script} Script]]",
            "",
            desc,
            "",
            "== Syntax ==",
            OPEN_SYNTAXHIGHLIGHT_EMITSENTINEL,
            #"<syntaxhighlight lang=\"papyrus\">",
            f"{self.return_type} Function {self.name}({self.params})".strip()
            + (f" {self.flags.strip()}" if self.flags else ""),
            #"</syntaxhighlight>",
            CLOSE_SYNTAXHIGHLIGHT_EMITSENTINEL,
        ]

        # Only emit Flags section for meaningful (non-trivial) flags
        if self.flags and self.flags.lower().strip() not in ("native", ""):
            markup += [
                "",
                "== Flags ==",
            ] + [f"*'''{flag.strip().capitalize()}'''" for flag in self.flags.split()]

        # Parameters
        markup += [
            "",
            "== Parameters ==",
            self._format_params(),
            "",
            "== Return Value ==",
            self._format_return_value(),
            "",
            "== Examples ==",
            self._format_examples(),
            "",
            "== See Also ==",
            f"*[[{parent_script} Script]]",
        ]

        # Add references (linked scripts mentioned in parameters/return types)
        for ref in sorted(self.references):
            markup.append(f"*[[{ref} Script]]")

        # Add sibling links — limited for brevity
        for sib in siblings[:3]:
            if sib != self.name:
                markup.append(f"*[[{sib} - {parent_script}|{sib}]]")
        
        markup.append(_generation_marker())
        return "\n".join(markup)

    # --- Enhanced Return Value phrasing ---
    def _format_return_value(self) -> str:
        """Generate more natural, descriptive return section text."""
        if not self.return_type or self.return_type.lower() == "none":
            return "None."
        linked_type = link_type(self.return_type)
        # if description already mentions what is returned, just clarify type
        if re.search(r"\breturn", self.description, re.IGNORECASE):
            return f"The function returns a {linked_type}."
        # Generic but human phrasing
        return f"The {linked_type} that this function returns."

    def _format_examples(self) -> str:
        """Return example block text or fallback template."""
        if self.examples:
            return OPEN_SYNTAXHIGHLIGHT_EMITSENTINEL + "\n" + "\n".join(self.examples) + "\n" + CLOSE_SYNTAXHIGHLIGHT_EMITSENTINEL

        # Attempt to suggest realistic placeholder
        sample_call = f"{self.name}({', '.join([p.split()[-1] for p in self.params.split(',') if p.strip()])})"
        return (
            OPEN_SYNTAXHIGHLIGHT_EMITSENTINEL + "\n" +
            f"; Example usage of {self.name}\n" +
            f"result = {sample_call}\n" +
            CLOSE_SYNTAXHIGHLIGHT_EMITSENTINEL
        )


    def _format_params(self) -> str:
        if not self.params.strip():
            return "None."
        parts = [p.strip() for p in self.params.split(",") if p.strip()]
        out = []
        for p in parts:
            pname = p.split()[-1]
            desc = self.param_docs.get(pname, "")
            out.append(f"*'''{p}'''" + (f": {desc}" if desc else ""))
        return "\n".join(out)



class PapyrusEvent:
    def __init__(self, name: str, params: str, description: str = "", param_docs: Dict[str, str] = None):
        self.name = name
        self.params = params
        self.description = description
        self.param_docs = param_docs or {}
        self.references: set[str] = set()

    def to_mediawiki(self, parent_script: str, siblings: List[str]) -> str:
        markup = [
            "[[Category:Scripting]]",
            "[[Category:Papyrus]]",
            "[[Category:Events]]",
            f"'''Member of:''' [[{parent_script} Script]]",
            "",
            self.description or f"Event called when {self.name} occurs.",
            "",
            "== Syntax ==",
            OPEN_SYNTAXHIGHLIGHT_EMITSENTINEL,
            f"Event {self.name}({self.params})",
            #"</syntaxhighlight>",
            CLOSE_SYNTAXHIGHLIGHT_EMITSENTINEL,
            "",
            "== Parameters ==",
            self._format_params(),
            "",
            "== Examples ==",
            OPEN_SYNTAXHIGHLIGHT_EMITSENTINEL,
            f"Event {self.name}({self.params})",
            f" Debug.Trace(\"{self.name} triggered\")",
            "endEvent",
            #"</syntaxhighlight>",
            CLOSE_SYNTAXHIGHLIGHT_EMITSENTINEL,
            "",
            "== See Also ==",
            f"*[[{parent_script} Script]]",
        ]
        for ref in sorted(self.references):
            markup.append(f"*[[{ref} Script]]")
        for sib in siblings[:3]:
            if sib != self.name:
                markup.append(f"*[[{sib} - {parent_script}|{sib}]]")
        return "\n".join(markup)

    def _format_params(self) -> str:
        if not self.params.strip():
            return "None."
        parts = [p.strip() for p in self.params.split(",") if p.strip()]
        out = []
        for p in parts:
            pname = p.split()[-1]
            desc = self.param_docs.get(pname, "")
            out.append(f"*'''{p}'''" + (f": {desc}" if desc else ""))
        return "\n".join(out)


class PapyrusScript:
    def __init__(self, name: str, extends: str):
        self.name = name
        self.extends = extends
        self.properties: List[PapyrusProperty] = []
        self.functions: List[PapyrusFunction] = []
        self.events: List[PapyrusEvent] = []
        self.structs: List[PapyrusStruct] = []

    def to_mediawiki(self) -> str:
        out = [
            f"'''Extends:''' [[{self.extends} Script]]",
            "",
            f"Script for manipulating {self.name} instances.",
            "",
        ]
        out.append("== Definition ==")
        out.append("<syntaxhighlight lang=\"papyrus\">")
        out.append(f"ScriptName {self.name} extends {self.extends} Native Hidden")
        #out.append("</syntaxhighlight>")
        out.append(CLOSE_SYNTAXHIGHLIGHT_EMITSENTINEL)
        out.append("")
        if self.extends:
            chain = [self.name]
            base = self.extends
            while base in KNOWN_TYPES:
                chain.insert(0, base)
                base = ""
            out.append("== Inheritance ==")
            out.append(" → ".join(chain))
            out.append("")
        out.append("== Summary ==")
        out.append("{| class=\"wikitable\"")
        out.append("! Category !! Count")
        out.append(f"|-\n| Properties || {len(self.properties)}")
        out.append(f"|-\n| Functions || {len(self.functions)}")
        out.append(f"|-\n| Events || {len(self.events)}")
        out.append("|}")
        out.append("")
        if self.structs:
            out.append("== Structs ==")
            for s in self.structs:
                out.append(s.to_mediawiki())
            out.append("")
        if self.properties:
            out.append("== Properties ==")
            globals_ = [p for p in self.properties if p.prop_type.lower() == "globalvariable"]
            others = [p for p in self.properties if p.prop_type.lower() != "globalvariable"]
            if globals_:
                out.append("=== Global Properties ===")
                for g in globals_:
                    out.append(g.to_mediawiki())
                out.append("")
            if others:
                out.append("=== Script Properties ===")
                for p in others:
                    out.append(p.to_mediawiki())
                out.append("")
        if self.functions:
            out.append("== Member Functions ==")
            for fn in self.functions:
                out.append(f"*Function [[{fn.name} - {self.name}|{fn.name}]]({fn.params})")
                if fn.description:
                    out.append(f"**{fn.description}")
            out.append("")
        if self.events:
            out.append("== Events ==")
            for ev in self.events:
                out.append(f"*Event [[{ev.name} - {self.name}|{ev.name}]]({ev.params})")
                if ev.description:
                    out.append(f"**{ev.description}")
            out.append("")
        out.append("[[Category:Scripting]]\n[[Category:Papyrus]]\n[[Category:Script Objects]]")
        out.append(_generation_marker())
        return "\n".join(out)



class DocSink:
    def write_script(self, script: "PapyrusScript"):
        raise NotImplementedError
    def write_function(self, script_name: str, fn: "PapyrusFunction"):
        raise NotImplementedError
    def write_event(self, script_name: str, ev: "PapyrusEvent"):
        raise NotImplementedError
    def write_misc(self, title: str, text: str):
        """Optional: write non-script pages (like indexes, readmes, etc.)."""
        raise NotImplementedError
    def finalize(self):
        pass

class SQLDocSink(DocSink):
    """
    Flexible SQL sink that supports SQLite and PostgreSQL.

    Accepts:
      - A connection string/path (str or Path)
      - An existing sqlite3.Connection or psycopg2 connection
    Automatically ensures tables exist and commits safely.
    """

    def __init__(
        self,
        conn: Union[str, Path, sqlite3.Connection],
        dialect: str = "sqlite",
        schema: Optional[str] = None,
        autocommit: bool = True,
    ):
        self.dialect = dialect.lower()
        self.schema = schema
        self.autocommit = autocommit

        # --- normalize connection ---
        if isinstance(conn, (str, Path)):
            conn_str = str(conn)
            if self.dialect == "sqlite":
                self.conn = sqlite3.connect(conn_str)
            elif self.dialect in ("postgres", "postgresql"):
                import psycopg2
                self.conn = psycopg2.connect(conn_str)
            else:
                raise ValueError(f"Unsupported SQL dialect: {self.dialect}")
        else:
            self.conn = conn  # already a live connection

        self.cur = self.conn.cursor()
        self._ensure_schema()


    def _ensure_schema(self):
        prefix = f"{self.schema}." if self.schema else ""
        id_type = "SERIAL PRIMARY KEY" if self.dialect.startswith("post") else "INTEGER PRIMARY KEY AUTOINCREMENT"

        ddl = [
            f"""
            CREATE TABLE IF NOT EXISTS {prefix}scripts (
                id {id_type},
                name TEXT,
                extends TEXT,
                summary TEXT
            );
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {prefix}functions (
                id {id_type},
                script_name TEXT,
                name TEXT,
                return_type TEXT,
                params TEXT,
                flags TEXT,
                description TEXT
            );
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {prefix}events (
                id {id_type},
                script_name TEXT,
                name TEXT,
                params TEXT,
                description TEXT
            );
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {prefix}misc_pages (
                id {id_type},
                title TEXT,
                content TEXT
            );
            """,
        ]
        for stmt in ddl:
            self.cur.execute(stmt)
        if self.autocommit:
            self.conn.commit()

    def write_misc(self, title: str, text: str):
        """Insert a general-purpose wiki page or metadata."""
        self._execute_safe(
            "INSERT INTO misc_pages (title, content) VALUES (?, ?)"
            if self.dialect == "sqlite"
            else "INSERT INTO misc_pages (title, content) VALUES (%s, %s)",
            (title, text),
        )


    def _execute_safe(self, query: str, params: tuple):
        """Execute a query and rollback if necessary."""
        try:
            self.cur.execute(query, params)
            if self.autocommit:
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise RuntimeError(f"SQLDocSink query failed: {e}") from e

 
    def write_script(self, script: "PapyrusScript"):
        self._execute_safe(
            "INSERT INTO scripts (name, extends, summary) VALUES (?, ?, ?)"
            if self.dialect == "sqlite"
            else "INSERT INTO scripts (name, extends, summary) VALUES (%s, %s, %s)",
            (script.name, script.extends, f"{len(script.functions)} funcs, {len(script.events)} events"),
        )

    def write_function(self, script_name: str, fn: "PapyrusFunction"):
        self._execute_safe(
            "INSERT INTO functions (script_name, name, return_type, params, flags, description) VALUES (?, ?, ?, ?, ?, ?)"
            if self.dialect == "sqlite"
            else "INSERT INTO functions (script_name, name, return_type, params, flags, description) VALUES (%s, %s, %s, %s, %s, %s)",
            (script_name, fn.name, fn.return_type, fn.params, fn.flags, fn.description),
        )

    def write_event(self, script_name: str, ev: "PapyrusEvent"):
        self._execute_safe(
            "INSERT INTO events (script_name, name, params, description) VALUES (?, ?, ?, ?)"
            if self.dialect == "sqlite"
            else "INSERT INTO events (script_name, name, params, description) VALUES (%s, %s, %s, %s)",
            (script_name, ev.name, ev.params, ev.description),
        )

  
    def finalize(self):
        try:
            self.conn.commit()
        except Exception:
            pass
        finally:
            try:
                self.cur.close()
            except Exception:
                pass
            try:
                self.conn.close()
            except Exception:
                pass


import io
import zipfile
import hashlib
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, ElementTree

class ArchiveDocSink(DocSink):
    """
    Collects all wiki pages in-memory, writes either a ZIP archive or a full MediaWiki XML dump.
    """

    def __init__(
        self,
        mode="zip",
        site_name="PapyrusDocs",
        base_url="http://localhost/wiki/Main_Page",
        contributor="ReedPapyri"
    ):
        self.mode = mode
        self.buffer = io.BytesIO()
        self.contributor = contributor

        if mode == "zip":
            # Standard ZIP archive mode
            self.zip = zipfile.ZipFile(self.buffer, "w", zipfile.ZIP_DEFLATED)
        elif mode == "xml":
            # MediaWiki XML export mode
            self._init_xml(site_name, base_url)
        else:
            raise ValueError("ArchiveDocSink mode must be 'zip' or 'xml'")

        self.page_id = 1
        self.rev_id = 1


    def _init_xml(self, site_name, base_url):
        self.root = Element(
            "mediawiki",
            {
                "xmlns": "http://www.mediawiki.org/xml/export-0.11/",
                "xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                "xsi:schemaLocation": "http://www.mediawiki.org/xml/export-0.11/ "
                "http://www.mediawiki.org/xml/export-0.11.xsd",
                "version": "0.11",
                "xml:lang": "en",
            },
        )

        # ── siteinfo header ──
        siteinfo = SubElement(self.root, "siteinfo")
        SubElement(siteinfo, "sitename").text = site_name
        SubElement(siteinfo, "dbname").text = "papyrus_wiki"
        SubElement(siteinfo, "base").text = base_url
        SubElement(siteinfo, "generator").text = "ReedPapyri 0.1"
        SubElement(siteinfo, "case").text = "first-letter"

        namespaces = SubElement(siteinfo, "namespaces")
        nsmap = {
            -2: "Media", -1: "Special", 0: "",
            1: "Talk", 2: "User", 3: "User talk", 4: site_name,
            5: f"{site_name} talk", 6: "File", 7: "File talk",
            8: "MediaWiki", 9: "MediaWiki talk", 10: "Template",
            11: "Template talk", 12: "Help", 13: "Help talk",
            14: "Category", 15: "Category talk"
        }
        for key, name in nsmap.items():
            SubElement(
                namespaces, "namespace", {"key": str(key), "case": "first-letter"}
            ).text = name


    def write_script(self, script: "PapyrusScript"):
        if self.mode == "zip":
            self.zip.writestr(f"{script.name} Script.wiki", script.to_mediawiki())
        else:
            self._add_xml_page(f"{script.name} Script", script.to_mediawiki())

    def write_function(self, script_name: str, fn: "PapyrusFunction"):
        if self.mode == "zip":
            self.zip.writestr(f"{fn.name} - {script_name}.wiki", fn.to_mediawiki(script_name, []))
        else:
            self._add_xml_page(f"{fn.name} - {script_name}", fn.to_mediawiki(script_name, []))

    def write_event(self, script_name: str, ev: "PapyrusEvent"):
        if self.mode == "zip":
            self.zip.writestr(f"{ev.name} - {script_name}.wiki", ev.to_mediawiki(script_name, []))
        else:
            self._add_xml_page(f"{ev.name} - {script_name}", ev.to_mediawiki(script_name, []))
            
    def write_misc(self, title: str, text: str):
        """Add arbitrary wiki page (like Category:Papyrus) to archive or XML."""
        safe_title = title.replace(":", "_")  # avoid invalid filenames in ZIP
        if self.mode == "zip":
            self.zip.writestr(f"{safe_title}.wiki", text)
        else:
            self._add_xml_page(title, text)


    def _add_xml_page(self, title, text):
        """Add a fully compliant <page> structure for MediaWiki import."""
        page = SubElement(self.root, "page")
        SubElement(page, "title").text = title
        SubElement(page, "ns").text = "0"
        SubElement(page, "id").text = str(self.page_id)
        self.page_id += 1

        revision = SubElement(page, "revision")
        SubElement(revision, "id").text = str(self.rev_id)
        self.rev_id += 1
        SubElement(revision, "timestamp").text = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

        contributor = SubElement(revision, "contributor")
        SubElement(contributor, "username").text = self.contributor
        SubElement(contributor, "id").text = "1"

        SubElement(revision, "model").text = "wikitext"
        SubElement(revision, "format").text = "text/x-wiki"

        sha1_hash = hashlib.sha1(text.encode("utf-8")).hexdigest()
        bytes_len = str(len(text.encode("utf-8")))

        text_el = SubElement(
            revision,
            "text",
            {"bytes": bytes_len, "sha1": sha1_hash, "xml:space": "preserve"},
        )
        text_el.text = text

        SubElement(revision, "sha1").text = sha1_hash


    def finalize(self):
        if self.mode == "zip":
            self.zip.close()
        elif self.mode == "xml":
            tree = ElementTree(self.root)
            tree.write(self.buffer, encoding="utf-8", xml_declaration=True)

    def get_bytes(self) -> bytes:
        """Return buffer contents (closes and finalizes first)."""
        self.finalize()
        self.buffer.seek(0)
        return self.buffer.getvalue()






class PapyrusParser:
    # Updated regex pattern to handle namespaces and colons in the script name and extends
    SCRIPT_PATTERN = re.compile(r"ScriptName\s+(?P<name>[A-Za-z0-9_:#]+)(\s+extends\s+(?P<extends>[A-Za-z0-9_:#]+))?", re.IGNORECASE)
    FUNC_PATTERN = re.compile(r"(?P<ret>\w+)\s+Function\s+(?P<name>\w+)\((?P<params>[^)]*)\)(?P<flags>.*)", re.IGNORECASE)
    EVENT_PATTERN = re.compile(r"Event\s+(?P<name>\w+)\((?P<params>[^)]*)\)", re.IGNORECASE)
    PROP_PATTERN = re.compile(r"(?P<type>\w+)\s+Property\s+(?P<name>\w+)\s+(?P<flags>auto|autoReadOnly|const)?", re.IGNORECASE)
    STRUCT_START = re.compile(r"Struct\s+(?P<name>\w+)", re.IGNORECASE)
    STRUCT_END = re.compile(r"EndStruct", re.IGNORECASE)
    STATE_START = re.compile(r"State\s+(?P<name>\w+)", re.IGNORECASE)
    STATE_END = re.compile(r"EndState", re.IGNORECASE)
    COMMENT_PATTERN = re.compile(r"^\s*;(.+)$")

    def parse(self, filepath: str) -> PapyrusScript:
        lines = Path(filepath).read_text(encoding="utf-8").splitlines()
        script = None
        current_desc, current_param_docs = [], {}
        in_struct, struct_name, struct_members = False, "", []
        current_state = None

        for line in lines:
            if m := self.SCRIPT_PATTERN.search(line):
                script_name = m.group("name")  # Use group() to access the matched group
                extends = m.group("extends") if m.group("extends") else ""  # Use group() and fallback to "" if extends is not found
                script = PapyrusScript(script_name, extends)
                continue
            if not script:
                continue
            if m := self.COMMENT_PATTERN.match(line):
                text = m[1].strip()
                if text.startswith("@param"):
                    _, pname, *pdesc = text.split(maxsplit=2)
                    current_param_docs[pname] = " ".join(pdesc)
                else:
                    current_desc.append(text)
                continue
                
            # Examples?
            if line.strip().startswith("; Example:"):
                # Attach example text to the most recently parsed function (if any)
                if script and script.functions:
                    script.functions[-1].examples.append(
                        line.strip().lstrip("; ").replace("Example:", "").strip()
                    )
                continue

            if in_struct:
                if self.STRUCT_END.search(line):
                    script.structs.append(PapyrusStruct(struct_name, struct_members, " ".join(current_desc)))
                    in_struct, struct_name, struct_members, current_desc = False, "", [], []
                else:
                    if line.strip():
                        struct_members.append(line.strip())
                continue
            if m := self.STRUCT_START.search(line):
                in_struct, struct_name = True, m["name"]
                continue
            if self.STATE_START.search(line):
                current_state = self.STATE_START.search(line)["name"]
                continue
            if self.STATE_END.search(line):
                current_state = None
                continue
            if m := self.PROP_PATTERN.search(line):
                script.properties.append(PapyrusProperty(m["name"], m["type"], m["flags"] or "", " ".join(current_desc)))
                current_desc, current_param_docs = [], {}
                continue
            if m := self.FUNC_PATTERN.search(line):
                script.functions.append(PapyrusFunction(
                    m["name"], m["ret"], m["params"], m["flags"].strip(),
                    " ".join(current_desc), dict(current_param_docs)
                ))
                current_desc, current_param_docs = [], {}
                continue
            if m := self.EVENT_PATTERN.search(line):
                ev = PapyrusEvent(
                    m["name"], m["params"], " ".join(current_desc), dict(current_param_docs)
                )
                if current_state:
                    ev.state = current_state
                script.events.append(ev)
                current_desc, current_param_docs = [], {}
                continue
        return script


# pro forma, trips on easy things like comments, namespace colon separators, etc. 
# intended to eventually handle exotic user scripts (the naive regex one chokes on) and things that are event heavy instead of function heavy
# i would vastly prefer peggy.js PEG parsing though... 
class PyParsingPapyrusParser(PapyrusParser):  

    from pyparsing import Word, alphas, alphanums, Literal, Group, delimitedList, ZeroOrMore, ParseException
    from pyparsing import Optional as parsingOptional


    # Token definitions using pyparsing
    SCRIPT_NAME = Word(alphas)
    EXTENDS_NAME = Word(alphas)
    PARAM_NAME = Word(alphas)
    FLAG = Word(alphas)
    TYPE_NAME = Word(alphas + ":#")  # Handle extended namespaces (e.g., spookytracktion:craneossikcontroller#vector)
    PROPERTY_ASSIGNMENT = Literal("=") + Word(alphanums + ".")
    FUNC_MODIFIER = Literal("native") | Literal("debugOnly")  # Captures function modifiers like 'native' or 'debugOnly'

    # Comment (single-line)
    COMMENT = Literal(";") + Word(alphas + ' ' + '0123456789')

    # Function: captures return type, function name, parameters (with default values), and modifiers
    RETURN_TYPE = Word(alphas)
    FUNC_NAME = Word(alphas)
    PARAMS = Group(delimitedList(PARAM_NAME + parsingOptional(Literal("=") + Word(alphanums + ".")("default_value"))))  # Parameters with optional default values
    FUNC_PARAMS = Group(delimitedList(PARAM_NAME + parsingOptional(Literal("=") + Word(alphanums + ".")("default_value"))))
    FUNCTION = RETURN_TYPE("return_type") + FUNC_NAME("function_name") + Literal("(") + FUNC_PARAMS("params") + Literal(")") + parsingOptional(FUNC_MODIFIER("modifier"))

    # Property: captures type, name, assignment, and flags
    PROP_TYPE = Word(alphas)
    PROP_NAME = Word(alphas)
    PROPERTY = PROP_TYPE("prop_type") + PROP_NAME("prop_name") + parsingOptional(PROPERTY_ASSIGNMENT) + parsingOptional(FLAG("flags"))

    # Event: captures event name and parameters
    EVENT = Literal("Event") + Word(alphas)("event_name") + Literal("(") + delimitedList(PARAM_NAME)("event_params") + Literal(")")

    # Struct start and end
    STRUCT_START = Literal("Struct") + Word(alphas)("struct_name")
    STRUCT_END = Literal("EndStruct")
    
    # State start and end
    STATE_START = Literal("State") + Word(alphas)("state_name")
    STATE_END = Literal("EndState")

    # Main parser: parses the entire script into script components
    SCRIPT_PARSER = Group(SCRIPT_NAME("script_name") + EXTENDS_NAME("extends") + ZeroOrMore(FUNCTION | PROPERTY | EVENT | STRUCT_START | STRUCT_END | STATE_START | STATE_END))

    def parse(self, filepath: str) -> 'PapyrusScript':
        lines = Path(filepath).read_text(encoding="utf-8").splitlines()
        script = None
        current_desc, current_param_docs = [], {}
        in_struct, struct_name, struct_members = False, "", []
        current_state = None
        
        try:
            # Iterate through lines and apply the parsing grammar to each line
            for line_number, line in enumerate(lines, 1):
                # Ignore empty lines
                if not line.strip():
                    continue

                try:
                    # Try to parse each line with the parser
                    parsed = self.SCRIPT_PARSER.parseString(line.strip(), parseAll=True)
                    
                    # Handle parsing results based on the type of match
                    if parsed.get("script_name"):
                        # If it's a Script definition
                        if not script:
                            script = PapyrusScript(parsed.script_name, parsed.extends)
                        continue
                    
                    if parsed.get("function_name"):
                        # If it's a function
                        script.functions.append(PapyrusFunction(
                            parsed.function_name,
                            parsed.return_type,
                            ', '.join([f"{param[0]}={param[1]}" if len(param) > 1 else param[0] for param in parsed.params]),
                            parsed.modifier or "",
                            " ".join(current_desc),
                            current_param_docs
                        ))
                        current_desc, current_param_docs = [], {}
                        continue
                    
                    if parsed.get("prop_name"):
                        # If it's a property
                        script.properties.append(PapyrusProperty(
                            parsed.prop_name,
                            parsed.prop_type,
                            parsed.flags or "",
                            " ".join(current_desc)
                        ))
                        current_desc, current_param_docs = [], {}
                        continue
                    
                    if parsed.get("event_name"):
                        # If it's an event
                        script.events.append(PapyrusEvent(
                            parsed.event_name,
                            ', '.join(parsed.event_params),
                            " ".join(current_desc),
                            current_param_docs
                        ))
                        current_desc, current_param_docs = [], {}
                        continue
                    
                    if parsed.get("struct_name"):
                        # If it's a struct definition
                        in_struct = True
                        struct_name = parsed.struct_name
                        continue
                    
                    if parsed.get("state_name"):
                        # If it's a state definition
                        current_state = parsed.state_name
                        continue
                    
                except ParseException as e:
                    print(f"Warning: Failed to parse line {line_number}: {line} - Error: {e}")
                    continue

        except Exception as e:
            print(f"Error parsing the script at {filepath}: {e}")
        
        return script




def generate_docs(input_path: str, output_target, mode: str = "wiki", parser_choice: str = "regular"):
    """
    Generate Papyrus documentation in one of four modes:
      'wiki' → write .wiki files to an output directory
      'sql'  → write to a SQLDocSink (keeps connection open for multiple scripts)
      'zip'  → write to an in-memory zip archive
      'xml'  → write to a MediaWiki XML dump
    """
    # Choose parser based on user input
    if parser_choice == "pyparsing":
        print(f"Using pyparsing parser...")
        parser = PyParsingPapyrusParser()
    else:
        parser = PapyrusParser()
        
    script = parser.parse(input_path)

    if script is None:
        print(f"❌ Failed to parse script: {input_path}")
        return None

    known_scripts = [f.name for f in script.functions] + [e.name for e in script.events]


    for fn in script.functions:
        for word in re.findall(r'\b[A-Z][A-Za-z0-9_]+\b', fn.params + " " + fn.return_type):
            if word != script.name and word not in known_scripts:
                fn.references.add(word)
    for ev in script.events:
        for word in re.findall(r'\b[A-Z][A-Za-z0-9_]+\b', ev.params):
            if word != script.name and word not in known_scripts:
                ev.references.add(word)


    if mode == "wiki":
        output_dir = Path(output_target)
        os.makedirs(output_dir, exist_ok=True)
        Path(output_dir, f"{script.name} Script.wiki").write_text(script.to_mediawiki(), encoding="utf-8")
        for fn in script.functions:
            Path(output_dir, f"{fn.name} - {script.name}.wiki").write_text(
                fn.to_mediawiki(script.name, [f.name for f in script.functions]), encoding="utf-8")
        for ev in script.events:
            Path(output_dir, f"{ev.name} - {script.name}.wiki").write_text(
                ev.to_mediawiki(script.name, [e.name for e in script.events]), encoding="utf-8")
        print(f"✅ Generated full docs for {script.name} → {output_dir}")
        return None

    elif mode == "sql":
        # Keep the same SQLDocSink instance alive for all scripts
        sink = output_target if isinstance(output_target, SQLDocSink) else SQLDocSink(output_target)
        sink.write_script(script)
        for fn in script.functions:
            sink.write_function(script.name, fn)
        for ev in script.events:
            sink.write_event(script.name, ev)
        # Do NOT finalize here; let the main caller handle it after all scripts
        print(f"✅ Stored {script.name} in SQL database")
        return sink

    elif mode in ("zip", "xml"):
        sink = output_target if isinstance(output_target, ArchiveDocSink) else ArchiveDocSink(mode=mode)
        sink.write_script(script)
        for fn in script.functions:
            sink.write_function(script.name, fn)
        for ev in script.events:
            sink.write_event(script.name, ev)
        print(f"✅ Added {script.name} to in-memory {mode.upper()} archive")
        return sink

    else:
        raise ValueError(f"Unknown output mode '{mode}'")





def generate_index(
    directory: str,
    user_type_file: Optional[str] = None,
    referenceProjectName: str = "Autogenerated",
    sink: Optional["DocSink"] = None,
):
    """Scan a folder for .psc or .wiki files and generate a master index with a sidebar.

    If a DocSink is provided, the index will be written into it via write_misc().
    Otherwise, it writes a Category:Papyrus.wiki file in the given directory.
    """
    merge_user_types(user_type_file)
    scripts = sorted({Path(p).stem for p in Path(directory).rglob("*.psc")})

    # Begin wiki table layout
    out_lines = [
        "__NOTOC__ __NOEDITSECTION__",
        "",
        '{|style="color:black;" width="100%" border="0" cellpadding="5" valign="top"',
        "|valign=\"top\"|",
        "",
        f"== Welcome to the {referenceProjectName} Papyrus Reference ==",
        "Papyrus is a lightweight, event-driven scripting system used for building gameplay logic and modular interactions, using Scripts as a sort of type or class, with elements of the language Pascal, UnrealScript, and C#/Java. "
        "This index is automatically generated from available .psc source files. Each linked script page includes member functions, events, and properties.",
        "",
        "== Papyrus Reference Index ==",
        "This page provides a concise, automatically generated listing of all Papyrus script reference pages in this documentation set.",
        "",
        "=== Script Objects ===",
    ]

    # Add all script pages
    for s in scripts:
        out_lines.append(f"* [[{s} Script]]")

    # Additional categories below the script list
    out_lines += [
        "",
        "=== Additional Categories ===",
        "* [[:Category:Scripting]]",
        "* [[:Category:Papyrus]]",
        "* [[:Category:Events]]",
        "* [[:Category:Script Objects|All Script Objects]]",
        "== Adding Custom Types ==",
        "You can extend this index by supplying a JSON file listing user-defined essential types. Example:",
        "<syntaxhighlight lang=\"json\">",
        "[\"MyCustomShip\", \"PlanetObject\", \"DockingPort\"]",
        "</syntaxhighlight>",
        "",
        "== See Also ==",
        "* [[Papyrus Language Reference]]",
        "* [[Variables and Properties (Papyrus)|Variables & Properties]]",
        "* [[Structs (Papyrus)|Structs]]",
        "* [[Operator Reference|Operators]]",
        "* [[Event Reference|Events]]",
        "",
        # --- Sidebar starts here ---
        '|style="color:black;" width="30%" border="0" cellpadding="5" valign="top"|',
        "== Papyrus Index ==",
        "=== Concepts ===",
        "* [[Differences_from_Previous_Scripting|Differences from Previous Scripting]]",
        "* [[Extending Scripts (Papyrus)|Extending Scripts]]",
        "* [[Persistence (Papyrus)|Persistence]]",
        "",
        "=== Language ===",
        "* [[Operator_Reference|Operators]]",
        "* [[Expression_Reference|Expressions]]",
        "* [[Statement_Reference|Statements]]",
        "* [[Function_Reference|Functions]]",
        "* [[States (Papyrus)|States]]",
        "",
        "=== Types ===",
        "* [[:Category:Script Objects|Objects]]",
        "* [[Variables and Properties (Papyrus)|Variables & Properties]]",
        "* [[Arrays (Papyrus)|Arrays]]",
        "* [[Structs (Papyrus)|Structs]]",
        "",
        "=== Events ===",
        "* [[:Category:Events|Events]]",
        "* [[Remote Papyrus Event Registration|Remote Event Registrations]]",
        "* [[Custom Papyrus Events|Custom Events]]",
        "",
        "=== External Text Editors ===",
        "* [[:Category:Text Editors|Choosing a Text Editor]]",
        "* [[Visual Studio Code]]",
        "",
        "=== Compiler ===",
        "* [[Papyrus Compiler Reference|Compiler Reference]]",
        "* [[Papyrus Compiler Errors|Papyrus Compiler Errors]]",
        "* [[:Category:Papyrus Configurations|Papyrus Configurations]]",
        "* [[Papyrus Projects]]",
        "",
        "=== Reference Pages ===",
        "* [[Papyrus FAQs]]",
        "* [[:Category:Papyrus Language Reference|Papyrus Language Reference]]",
        "* [[Papyrus Runtime Errors]]",
        "* [[INI Settings (Papyrus)|Papyrus-related INI Settings]]",
        "* [[Game Settings (Papyrus)|Papyrus-Related Game Settings]]",
        "* [[Console Commands (Papyrus)|Papyrus-Related Console Commands]]",
        "* [[Papyrus_Glossary|Glossary of Terms]]",
        "|-",
        "|colspan=2|",
        "|}",
        "",
        "[[Category:Scripting]]",
        "[[Category:Papyrus]]",
        "[[Category:Script Objects]]",
    ]

    # Final content
    index_title = "Category:Papyrus"
    index_text = "\n".join(out_lines)

    # Write into sink if available, otherwise to filesystem
    if sink:
        sink.write_misc(index_title, index_text)
        print(f"✅ Added index page → {index_title} (via {sink.__class__.__name__})")
    else:
        out_path = Path(directory) / f"{index_title}.wiki"
        out_path.write_text(index_text, encoding="utf-8")
        print(f"✅ Wrote index page with sidebar → {out_path}")





class PapyrusForeignDecompilerAutomation:
    """
    Scans a directory for .pex files and attempts to decompile them
    into .psc files using any compatible decompiler executable.

    The tool detects whether it must use Wine/Proton or can run natively,
    depending on platform and the binary type. It runs only when
    --preproc-foreign-decompiler is explicitly provided.
    """

    def __init__(
        self,
        decompiler_path: str,
        force: bool = False,
        runner_hint: Optional[str] = None,
        env: Optional[dict] = None,
    ):
        """
        :param decompiler_path: Path to the decompiler executable (any tool).
        :param force: Re-decompile even if PSC is newer than PEX.
        :param runner_hint: Optional command (e.g. "wine", "proton", "bottles-cli run").
        :param env: Optional environment variables to inject (e.g. WINEPREFIX).
        """
        self.decompiler_path = Path(decompiler_path).resolve()
        self.force = force
        self.env = os.environ.copy()
        if env:
            self.env.update(env)
        self.runner_hint = runner_hint
        self.is_windows = platform.system().lower().startswith("win")
        self.runner = self._detect_runner()



    def _detect_runner(self) -> Optional[List[str]]:
        """Determine how to execute the decompiler (native vs compatibility layer)."""
        if self.is_windows:
            return None  # run directly

        # If user specified a runner (e.g. proton, wine64, bottles)
        if self.runner_hint:
            parts = self.runner_hint.split()
            if shutil.which(parts[0]):
                return parts
            print(f"⚠️ Runner '{self.runner_hint}' not found in PATH.")
            return None

        # Otherwise, auto-detect based on binary type
        if not self.decompiler_path.exists():
            print(f"❌ Decompiler binary not found: {self.decompiler_path}")
            return None

        try:
            result = subprocess.run(
                ["file", "-b", str(self.decompiler_path)],
                capture_output=True,
                text=True,
                check=True,
            )
            desc = result.stdout.lower()
            if "pe32" in desc or "pe64" in desc:
                # Windows binary — try Wine or Proton
                for candidate in ("wine64", "wine", "proton", "bottles-cli"):
                    if shutil.which(candidate):
                        print(f"🔧 Detected Windows binary — using {candidate}")
                        return [candidate]
                print("⚠️  No compatible runner (Wine/Proton) found for Windows binary.")
                return None
            else:
                # Native binary, run directly
                return None
        except Exception:
            # Fallback: try Wine if exists
            if shutil.which("wine"):
                return ["wine"]
            return None

    def _should_skip(self, pex: Path, psc: Path) -> bool:
        """Skip re-decompiling if PSC exists and is newer (unless force=True)."""
        if self.force:
            return False
        return psc.exists() and psc.stat().st_mtime > pex.stat().st_mtime



    def _decompile_one(self, pex: Path) -> Optional[Path]:
        """Run the configured decompiler on a single .pex file."""
        if not self.decompiler_path.exists():
            print(f"❌ Decompiler not found: {self.decompiler_path}")
            return None

        expected_psc = pex.with_suffix(".psc")
        if self._should_skip(pex, expected_psc):
            print(f"⏩ Skipping {pex.name} (already decompiled and up-to-date)")
            return expected_psc

        print(f"🧩 Decompiling {pex.name}...")

        # Build command
        if self.runner:
            cmd = [*self.runner, str(self.decompiler_path), str(pex)]
        else:
            cmd = [str(self.decompiler_path), str(pex)]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, env=self.env)
            if result.stdout.strip():
                print(result.stdout.strip())
        except subprocess.CalledProcessError as e:
            print(f"⚠️  Failed to decompile {pex.name}: {e.stderr.strip() or e.stdout.strip()}")
            return None

        if expected_psc.exists():
            print(f"✅ Decompiled → {expected_psc}")
            return expected_psc
        else:
            print(f"⚠️  Expected output not found: {expected_psc}")
            return None



    def find_pex_files(self, directory: str) -> List[Path]:
        """Recursively locate all .pex files."""
        return sorted(Path(directory).rglob("*.pex"))

    def run(self, directory: str) -> List[Path]:
        """Decompile all .pex files in a directory tree."""
        print(f"🔍 Searching for .pex files under: {directory}")
        pex_files = self.find_pex_files(directory)
        if not pex_files:
            print("ℹ️  No .pex files found.")
            return []

        generated: List[Path] = []
        for pex in pex_files:
            psc = self._decompile_one(pex)
            if psc:
                generated.append(psc)

        print(f"✅ Decompilation complete. {len(generated)} .psc files ready.")
        return generated


if __name__ == "__main__":
    import argparse
    import sys
    import traceback
    from pathlib import Path
    from datetime import datetime

    print("🔧 ReedPapyri — Papyrus Documentation & Wiki Toolchain")

    ap = argparse.ArgumentParser(
        description="Papyrus docgen / auto-linking MediaWiki toolchain for BGS games or their mods (supports wiki, sql, zip, and xml outputs)"
    )

    ap.add_argument(
        "psc_or_dir",
        help="Path to a .psc file or folder (e.g. '.' if you are in the directory where you have your .psc files)",
    )
    ap.add_argument(
        "out",
        help="Output directory or target file (e.g., './Output' or 'StarbaseWiki3')",
    )

    ap.add_argument(
        "--mode",
        choices=["wiki", "sql", "zip", "xml"],
        default="wiki",
        help="Output mode: wiki, sql, zip, or xml",
    )
    ap.add_argument("--db-conn", help="SQL connection string or path (required if mode=sql)")
    ap.add_argument("--db-dialect", choices=["sqlite", "postgres"], default="sqlite",
                    help="Database dialect for SQL mode")

    ap.add_argument("--index", action="store_true", help="Generate index (Category:Papyrus) after docs")
    ap.add_argument("--user-types", help="Path to JSON file of user-defined types for linking")
    ap.add_argument("--project-name", default="PapyrusDocs", help="Project name for index or Docker setup")

    ap.add_argument("--docker", action="store_true", help="Generate docker-compose.yml for hosting docs")
    ap.add_argument("--ssl", action="store_true", help="Enable HTTPS with Caddy")
    ap.add_argument("--domain", help="Domain for HTTPS setup (required if --ssl is used)")
    ap.add_argument("--email", help="Email for Let's Encrypt SSL")
    ap.add_argument("--local-ssl", action="store_true", help="Use local/internal certs")
    ap.add_argument("--db", action="store_true", help="Include database container in docker-compose")
    ap.add_argument("--no-docgen", dest="include_docgen", action="store_false", help="Skip docgen container")
    ap.add_argument("--build-docgen", action="store_true", help="Build docgen from Dockerfile.docgen")

    ap.add_argument("--wiki-user", default="ReedPapyri", help="Contributor username for XML exports")
    ap.add_argument("--wiki-base", default="http://papyruswiki.localhost/wiki/Main_Page",
                    help="Base URL for the MediaWiki site in XML exports")
    ap.add_argument("--install-syntax-highlighting", action="store_true",
                help="Attempt to build and install Papyrus syntax highlighting in MediaWiki SyntaxHighlight_GeSHi (happens outside the container in ./extensions, warning)")

                    
    ap.add_argument(
    "--no-marker",
     action="store_true",
     help="Do not include invisible generation markers in wiki output",
    )
    
    ap.add_argument(
    "--no-marker-seconds",
    action="store_true",
    help="Truncate generation marker timestamps to minutes (less noisy diffs)",
    )
    
    # Add this to your argument parser
    ap.add_argument(
        "--syntax-language",
        help="Specify the language for syntax highlighting (e.g., 'papyrus', 'AutoIt', 'pascal').",
        default="papyrus",  # Default to Papyrus if not specified
    )


    ap.add_argument(
        "--preproc-foreign-decompiler",
        action="store_true",
        help="Enable preprocessing step to decompile .pex files before docgen."
    )
    ap.add_argument(
        "--foreign-decompiler-path",
        default="./Decompiler.exe",
        help="Path to the external decompiler executable (EXE or native binary)."
    )
    ap.add_argument(
        "--foreign-decompiler-runner",
        help="Optional execution wrapper for non-Windows environments (e.g. 'wine', 'proton run', 'bottles-cli run')."
    )
    ap.add_argument(
        "--foreign-decompiler-force-decompile",
        action="store_true",
        help="Force re-decompilation even if the existing .psc is newer than the .pex."
    )
    ap.add_argument(
        "--foreign-decompiler-env",
        nargs="*",
        help="Extra environment variables for the decompiler (e.g. WINEPREFIX=~/.wine WINEDEBUG=-all)."
    )

    ap.add_argument(
        "--parser",
        choices=["regular", "pyparsing"],
        default="regular",
        help="Select the parser to use: 'regular' (default) or 'pyparsing'."
    )

    args = ap.parse_args()
    
    # Get the selected parser choice from the arguments
    parser_choice = args.parser
 
    if args.docker:
        if args.mode != "xml":
            print(f"⚠️ Docker setup detected. Forcing mode to 'xml' and removing timestamp for easy import & bind mounting.")
            args.mode = "xml"
            
    # Get the language argument from the user input
    highlighting_language = args.syntax_language

    # Apply the specified language for syntax highlighting
    remap_syntaxhighlight(highlighting_language)

    
    if args.no_marker:
        INCLUDE_GENERATION_MARKER = False
        print("ℹ️ Generation markers disabled for this run.")
        
    if args.no_marker_seconds:
        INCLUDE_MARKER_SECONDS = False
        print("ℹ️ Generation marker timestamps limited to minutes precision.")

    input_path = Path(args.psc_or_dir)
    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_path.exists():
        sys.exit(f"❌ Input path not found: {input_path}")


    if args.mode == "sql":
        if not args.db_conn:
            sys.exit(
                "❌ In SQL mode you must specify a database connection.\n"
                "   For SQLite:   --db-conn ./Output/PapyrusDocs.db\n"
                "   For Postgres: --db-conn 'dbname=papyrus user=admin password=secret host=localhost'"
            )

        if args.db_dialect == "sqlite":
            db_path = Path(args.db_conn)
            if db_path.exists() and db_path.is_dir():
                sys.exit(f"❌ '{args.db_conn}' is a directory, not a SQLite database file.")
            db_path.parent.mkdir(parents=True, exist_ok=True)
        elif args.db_dialect == "postgres" and "=" not in args.db_conn:
            sys.exit(
                "❌ Invalid PostgreSQL connection string.\n"
                "   Example: --db-conn 'dbname=papyrus user=admin password=secret host=localhost'"
            )


    sink = None
    try:
        if args.mode == "xml":
            sink = ArchiveDocSink(
                mode="xml",
                site_name=args.project_name,
                base_url=args.wiki_base,
                contributor=args.wiki_user,
            )
        elif args.mode == "zip":
            sink = ArchiveDocSink(mode="zip")
        elif args.mode == "sql":
            sink = SQLDocSink(args.db_conn, dialect=args.db_dialect)
            # Test connection
            try:
                sink.cur.execute("SELECT 1;")
                sink.conn.commit()
            except Exception as e:
                sys.exit(f"❌ Database connection test failed: {e}")
    except Exception as e:
        traceback.print_exc()
        sys.exit(f"❌ Failed to initialize output sink: {e}")
        
    if args.preproc_foreign_decompiler:
        print("⚙️ Running foreign decompiler preprocessor...")
        env = dict(e.split("=", 1) for e in args.foreign_decompiler_env) if args.foreign_decompiler_env else None
        PapyrusForeignDecompilerAutomation(
            decompiler_path=args.foreign_decompiler_path,
            force=args.foreign_decompiler_force_decompile,
            runner_hint=args.foreign_decompiler_runner,
            env=env,
        ).run(str(input_path))

    total_scripts = 0
    try:
        if input_path.is_file():
            print(f"📄 Parsing single file: {input_path.name}")
            generate_docs(str(input_path), sink or args.out, args.mode, parser_choice)
            total_scripts = 1
        else:
            print(f"📂 Scanning directory: {input_path}")
            psc_files = list(input_path.rglob("*.psc"))
            if not psc_files:
                print("⚠️ No .psc files found.")
            for psc_file in psc_files:
                print(f"📄 Parsing {psc_file}")
                generate_docs(str(psc_file), sink or args.out, args.mode, parser_choice)
                total_scripts += 1
    except Exception as e:
        print(f"❌ Error while generating docs: {e}")
        traceback.print_exc()
        sys.exit(1)
        
    if args.index:
        try:
            generate_index(
                args.out,
                args.user_types,
                args.project_name,
                sink=sink if sink else None,
            )
        except Exception as e:
            print(f"⚠️ Failed to generate index: {e}")


    # This section writes the output based on the sink type (XML, SQL, etc.)
    if isinstance(sink, ArchiveDocSink):
        # Force the name to be PapyrusDocs.xml for Docker
        if args.docker:
            archive_name = "PapyrusDocs.xml"  # Fix the name for Docker usage
        else:
            # Keep timestamped name for non-Docker cases
            archive_name = f"{args.project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{args.mode}"
        
        output_file = output_dir / archive_name  # Define the output path
        
        with open(output_file, "wb") as f:
            f.write(sink.get_bytes())  # Write the bytes to the file
        print(f"📦 Wrote {args.mode.upper()} archive → {output_file}")

    elif isinstance(sink, SQLDocSink):
        try:
            sink.finalize()
            print(f"💾 Saved SQL database → {getattr(sink.conn, 'database', args.db_conn)}")
        except Exception as e:
            print(f"⚠️ Failed to finalize SQL sink: {e}")

    if args.docker:
        print("\n⚠️  SECURITY NOTICE:")
        print("This operation may help set up Docker containers and related code for:")
        print("  - MediaWiki (MediaWiki base image)")
        print("  - Caddy (reverse proxy and SSL automation)")
        print("  - pygmentize (syntax highlighting binary)")
        print("  - SyntaxHighlight(_GeSHi) (MediaWiki syntax plugin)")
        print("")
        print("These components are downloaded from external sources and may execute third-party code.")
        print("They could be subject to supply chain vulnerabilities or version changes.")
        print("Only proceed if you trust the sources and have reviewed the Dockerfiles or images.")
        print("")

        confirm = input("Type 'yes' to continue, or anything else to cancel: ").strip().lower()
        if confirm != "yes":
            print("❌ Operation cancelled by user for safety.")
        else:
            try:
                if args.ssl and not args.domain:
                    print("⚠️ SSL requested but no domain provided — skipping Caddy setup.")
                PapyrusDockerComposeBasicSQLLiteVersion(
                    project_name=args.project_name,
                    output_dir=args.out,
                    enable_ssl=args.ssl,
                    domain=args.domain,
                    email=args.email,
                    db_enabled=args.db,
                    local_ssl=args.local_ssl,
                    include_docgen=args.include_docgen,
                    build_docgen=args.build_docgen,
                    install_syntax_highlighting=args.install_syntax_highlighting,
                ).generate()
                print(f"🐳 Docker environment generated for {args.project_name}")
            except Exception as e:
                print(f"⚠️ Docker generation failed: {e}")


    print(f"✅ Completed: {total_scripts} Papyrus scripts processed in mode '{args.mode}'.")
    print("🎆 Done.")




