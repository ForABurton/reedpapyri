import io
import json
import os
import re
import shutil
import sqlite3
import struct
import subprocess
import sys
import textwrap
import zipfile
import hashlib
import zlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Union, Optional
from xml.etree.ElementTree import Element, SubElement, ElementTree
import platform
import tempfile

import yaml


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




@dataclass
class SyntaxHighlightConfig:
    """Config for MediaWiki syntax highlighting extension and Papyrus lexer."""
    extension: str = "SyntaxHighlight_GeSHi"
    dir: str = "/var/www/html/extensions/SyntaxHighlight_GeSHi"
    bundle: str = "/var/www/html/extensions/SyntaxHighlight_GeSHi/pygments/pygmentize"
    update_lexers: str = "/var/www/html/extensions/SyntaxHighlight_GeSHi/maintenance/updateLexerList.php"
    update_css: str = "/var/www/html/extensions/SyntaxHighlight_GeSHi/maintenance/updateCSS.php"
    pygments_style_name: str = "papyrus"




from pathlib import Path
import textwrap


class PapyrusLexerInjectorGenerator:
    """
    Generates a fully functional, self-contained Papyrus lexer injector script
    (equivalent to papyruslexerconjecture.py) for MediaWiki's SyntaxHighlight_GeSHi.
    """

    def __init__(self, output_path: str = "papyruslexerconjecture.py"):
        self.output_path = Path(output_path)

    def generate_code(self) -> str:
        """Return the complete injector script source as a string."""
        return textwrap.dedent(r"""\
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import zipfile
import subprocess
import textwrap
import time
import threading
import tempfile
import shutil
from pathlib import Path

PYGMENTIZE_BUNDLE = "/var/www/html/extensions/SyntaxHighlight_GeSHi/pygments/pygmentize"
UPDATE_LEXERS = "/var/www/html/extensions/SyntaxHighlight_GeSHi/maintenance/updateLexerList.php"
UPDATE_CSS = "/var/www/html/extensions/SyntaxHighlight_GeSHi/maintenance/updateCSS.php"

LEXER_CODE = textwrap.dedent(r'''\

from pygments.lexer import RegexLexer, bygroups
from pygments.token import Text, Comment, Keyword, Name, String, Number, Operator, Punctuation

__all__ = ["PapyrusLexer"]

class PapyrusLexer(RegexLexer):
    name = "Papyrus"
    aliases = ["papyrus", "psc"]
    filenames = ["*.psc"]
    mimetypes = ["text/x-papyrus"]

    tokens = {
        "root": [

            (r"\s+", Text),
            (r";.*?$", Comment.Single),
            (r"/;.*?;/", Comment.Multiline),

            (
                r'(?i)\b(scriptname|extends|import|property|endproperty|auto|const|'
                r'function|endfunction|event|endevent|state|endstate|struct|endstruct|'
                r'if|elseif|else|endif|while|endwhile|return|new|as)\b',
                Keyword
            ),
              
            (r'(?i)\b(None|True|False)\b', Keyword.Constant),

            (r'(?i)\b(ObjectReference|Actor|Quest|Alias|Form|Armor|Weapon|Race|'
             r'MagicEffect|Activator|Sound|Static|GlobalVariable|ImageSpaceModifier)\b',
             Name.Builtin),

            (r"\b\d+\.\d+\b", Number.Float),
            (r"\b\d+\b", Number.Integer),

            (r'"([^"\\]|\\.)*"', String),

            (r'==|!=|<=|>=|[-+/*%=<>!]', Operator),
            (r'[()\[\]{},.:]', Punctuation),

            (r'([A-Za-z_][A-Za-z0-9_]*)(:)([A-Za-z_][A-Za-z0-9_]*)',
            bygroups(Name.Namespace, Punctuation, Name.Class)),

            (r'[A-Za-z_][A-Za-z0-9_#]*', Name),
        ]
    }
''')

STYLE_CODE = textwrap.dedent('''\
from pygments.style import Style
from pygments.token import Text, Comment, Keyword, Name, String, Number, Operator, Punctuation

__all__ = ["PapyrusStyle"]

class PapyrusStyle(Style):
    default_style = ""
    background_color = "#1E1E1E"
    styles = {
        Text: "#DCDCDC",
        Comment: "italic #6A9955",
        Keyword: "bold #569CD6",
        Keyword.Constant: "bold #D19A66",
        Name.Builtin: "#4EC9B0",
        Name.Namespace: "bold #9CDCFE",
        Name.Class: "#9CDCFE",
        Name: "#DCDCAA",
        String: "#CE9178",
        Number: "#B5CEA8",
        Operator: "#D4D4D4",
        Punctuation: "#D4D4D4",
    }
''')

MAPPING_INSERTION = (
    "    'PapyrusLexer': ('pygments.lexers.papyrus', 'Papyrus', "
    "('papyrus', 'psc'), ('*.psc',), ('text/x-papyrus',)),\n"
)

def ensure_bundle_exists():
    if not os.path.exists(PYGMENTIZE_BUNDLE):
        sys.exit(f"[❌] Cannot find pygmentize bundle at {PYGMENTIZE_BUNDLE}")
    print(f"[✔] Found existing pygmentize bundle.")

def inject_files():
    print("[🧩] Injecting Papyrus lexer and style into Pygments bundle...")
    tmp = tempfile.mkdtemp(prefix="pyg_patch_")
    with zipfile.ZipFile(PYGMENTIZE_BUNDLE, "r") as zf:
        zf.extractall(tmp)

    Path(tmp, "pygments/lexers/papyrus.py").write_text(LEXER_CODE, encoding="utf-8")
    Path(tmp, "pygments/styles/papyrus.py").write_text(STYLE_CODE, encoding="utf-8")

    with zipfile.ZipFile(PYGMENTIZE_BUNDLE, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(tmp):
            for f in files:
                fp = os.path.join(root, f)
                rel = os.path.relpath(fp, tmp)
                zf.write(fp, rel)
    shutil.rmtree(tmp)
    print("   → Added pygments/lexers/papyrus.py")
    print("   → Added pygments/styles/papyrus.py")

def patch_mapping():
    print("[🧬] Patching pygments/lexers/_mapping.py to add PapyrusLexer after AutoItLexer...")
    autoit_key = "'AutoItLexer':"
    tmp = tempfile.mkdtemp(prefix="pyg_patch_")
    try:
        with zipfile.ZipFile(PYGMENTIZE_BUNDLE, "r") as zf:
            zf.extractall(tmp)
        mapping_path = Path(tmp, "pygments/lexers/_mapping.py")
        data = mapping_path.read_text(encoding="utf-8")
        if "PapyrusLexer" in data:
            print("[ℹ️] PapyrusLexer already present; skipping patch.")
        else:
            if autoit_key not in data:
                print("[⚠️] AutoItLexer entry not found — inserting at end instead.")
                new_data = data.rstrip() + "\n" + MAPPING_INSERTION + "\n"
            else:
                lines = data.splitlines(keepends=True)
                new_lines = []
                for line in lines:
                    new_lines.append(line)
                    if autoit_key in line:
                        new_lines.append(MAPPING_INSERTION)
                new_data = "".join(new_lines)
            mapping_path.write_text(new_data, encoding="utf-8")

        # rebuild the bundle cleanly
        with zipfile.ZipFile(PYGMENTIZE_BUNDLE, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(tmp):
                for f in files:
                    fp = os.path.join(root, f)
                    rel = os.path.relpath(fp, tmp)
                    zf.write(fp, rel)
        print("[✅] Successfully added PapyrusLexer to _mapping.py.")
    except Exception as e:
        print(f"[❌] Failed to patch mapping: {e}")
    finally:
        shutil.rmtree(tmp)

def verify_bundle():
    print("[🔎] Verifying Pygments bundle integrity...")
    env = os.environ.copy()
    # Tell Python to import from the MediaWiki pygmentize zip first (this isn't system installed!)
    env["PYTHONPATH"] = f"/var/www/html/extensions/SyntaxHighlight_GeSHi/pygments/pygmentize:{env.get('PYTHONPATH', '')}"
    try:
        subprocess.run(
            ["python3", "-m", "pygments", "-L", "lexers"],
            env=env,
            check=True,
            capture_output=True,
        )
        print("[✅] Pygments bundle verified successfully.")
    except subprocess.CalledProcessError as e:
        print("[❌] Bundle verification failed:")
        print(e.stderr.decode(errors="ignore"))
        sys.exit(1)

def reapp_bundle():
    print("[⚙️] Rebuilding pygmentize bundle as a self-contained zipapp...")

    import zipapp

    tmp = tempfile.mkdtemp(prefix="pyg_repack_")
    try:
        # Extract current bundle to temp
        with zipfile.ZipFile(PYGMENTIZE_BUNDLE, "r") as zf:
            zf.extractall(tmp)

        # Rebuild using zipapp to add a proper shebang
        zipapp.create_archive(
            source=tmp,
            target=PYGMENTIZE_BUNDLE,
            interpreter="/usr/bin/env python3"
        )
        os.chmod(PYGMENTIZE_BUNDLE, 0o755)

        print("[✅] Bundle rebuilt and executable restored.")
    except Exception as e:
        print(f"[❌] Failed to rebuild pygmentize zipapp: {e}")
        sys.exit(1)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_highlight_papyrus():

    sample_path = "/var/www/html/extensions/SyntaxHighlight_GeSHi/Example.psc"
    sample_code = textwrap.dedent('''\
Scriptname Example extends Quest

int property PlayerLevel auto
string property Greeting auto

Event OnInit()
    Debug.Trace("Example script initialized!")
    PlayerLevel = Game.GetPlayer().GetLevel()
    if PlayerLevel > 10
        Greeting = "Welcome back, seasoned adventurer!"
    else
        Greeting = "Greetings, novice hero."
    endif
    SayGreeting()
EndEvent

Function SayGreeting()
    Debug.Notification(Greeting)
EndFunction
    ''')

    Path(sample_path).write_text(sample_code, encoding="utf-8")
    print(f"[🧪] Testing Papyrus highlighting → {sample_path}")
    subprocess.run(
        [
            "python3",
            "/var/www/html/extensions/SyntaxHighlight_GeSHi/pygments/pygmentize",
            "-l", "papyrus",
            "-f", "terminal256",
            "-O", "style=papyrus",
            sample_path,
        ],
        check=False,
    )
    subprocess.run(["python3","/var/www/html/extensions/SyntaxHighlight_GeSHi/pygments/pygmentize","-l", "autoit","-f", "terminal256", "-O", "style=default", sample_path],check=False)
   
    print("[✅] Papyrus highlighting test completed.\n")

def regenerate_mediawiki_data():
    print("[🧠] Triggering MediaWiki SyntaxHighlight regeneration...")
    subprocess.run(["php", UPDATE_LEXERS], check=False)
    env = os.environ.copy()
    env["PYGMENTS_STYLE"] = "papyrus"
    subprocess.run(["php", UPDATE_CSS], check=False, env=env)
    print("[✅] MediaWiki SyntaxHighlight lexers and CSS refreshed.")

def delayed_regeneration():
    print("[⏱] Waiting 20 seconds before background re-registration...")
    sys.stdout.flush()
    time.sleep(20)
    regenerate_mediawiki_data()
    print("[✅] Background MediaWiki regeneration complete.")

def main():
    ensure_bundle_exists()
    print("[🔍] Checking if Papyrus already injected...")
    with zipfile.ZipFile(PYGMENTIZE_BUNDLE, "r") as zf:
        names = zf.namelist()
    if "pygments/lexers/papyrus.py" in names:
        print("[ℹ️] Papyrus lexer already in bundle — patching mapping and regenerating only.")
    else:
        inject_files()
    patch_mapping()
    verify_bundle()
    reapp_bundle()
    regenerate_mediawiki_data()
    test_highlight_papyrus()

    try:
        threading.Thread(target=delayed_regeneration, daemon=True).start()
        print("[🚀] Scheduled background regeneration.")
    except Exception as e:
        print(f"[⚠️] Could not start delayed regeneration: {e}")

if __name__ == "__main__":
    main()
""").lstrip()

    def write(self):
        """Write the generated script to disk."""
        code = self.generate_code()
        self.output_path.write_text(code, encoding="utf-8")
        os.chmod(self.output_path, 0o755)
        print(f"🧬 Generated Papyrus lexer injector → {self.output_path}")



def ensure_dummy_png(path: str, color=(255, 255, 255, 255), size=(160, 160)):
    """
    Generate a valid PNG using only the Python standard library.
    Produces an image of `size` (default: 160x160), filled with RGBA `color`.
    """

    path = Path(path)
    if path.exists():
        print(f"✔ Existing PNG found at {path}")
        return

    width, height = size
    png_sig = b"\x89PNG\r\n\x1a\n"

    # IHDR: image header chunk
    ihdr_data = struct.pack("!2I5B", width, height, 8, 6, 0, 0, 0)
    ihdr = b"IHDR" + ihdr_data
    ihdr_crc = struct.pack("!I", zlib.crc32(ihdr) & 0xffffffff)
    ihdr_chunk = struct.pack("!I", len(ihdr_data)) + ihdr + ihdr_crc

    # Build raw image data: each scanline starts with filter byte 0
    pixel = bytes(color)
    row = b"\x00" + pixel * width
    raw_image = row * height
    compressed = zlib.compress(raw_image)

    # IDAT: image data chunk
    idat = b"IDAT" + compressed
    idat_crc = struct.pack("!I", zlib.crc32(idat) & 0xffffffff)
    idat_chunk = struct.pack("!I", len(compressed)) + idat + idat_crc

    # IEND: image end chunk
    iend = b"IEND"
    iend_crc = struct.pack("!I", zlib.crc32(iend) & 0xffffffff)
    iend_chunk = struct.pack("!I", 0) + iend + iend_crc

    # Combine all
    png_data = png_sig + ihdr_chunk + idat_chunk + iend_chunk
    path.write_bytes(png_data)
    print(f"🖼️ Generated dummy {width}x{height} PNG at {path}")

class PapyrusDockerComposeUnattendedSQLDatabaseVersion:
    """
    Generates a docker-compose.yml for an unattended MediaWiki + MariaDB deployment,
    with automatic Papyrus lexer injection and optional first-run import.

    Drop-in replacement for PapyrusDockerComposeBasicSQLLiteVersion
    with parameterized SQL backend, ports, syntax highlight extension, and more.
    """

    def __init__(
        self,
        output_dir: str,
        project_name: str = "papyrus_wiki",
        db_image: str = "mariadb:11",
        mw_image: str = "mediawiki:1.44",
        mw_http_port: int = 40201,
        db_port: int = 30433,
        mw_dbname: str = "wikidb",
        mw_dbuser: str = "wikiuser",
        mw_dbpass: str = "wikipass",
        mw_rootpass: str = "rootpass",
        mw_admin_user: str = "papyrusdocadmin",
        mw_admin_pass: str = "papyrusdocadminpass",
        mw_site_name: str = "Papyrus Docs Wiki",
        mw_site_lang: str = "en",
        mw_server: str = "http://localhost:40201",
        mw_extensions: List[str] = None,
        mw_skins: List[str] = None,
        enable_autoimport: bool = True,
        autoimport_marker: str = ".autoimportdone",
        syntax_config: SyntaxHighlightConfig = None,
        python_injector_script: str = "./papyruslexerconjecture.py",
        injector_mount_path: str = "/papyruslexerconjecture.py",
        wiki_logo_path: str = "./wiki.png",
        auto_import_xml: str = "./AutoFirstRunImport.xml",
        docker_volume_name: str = "mediawiki_unattended_mariadb_data",
        php_modules: List[str] = None,
        sleep_time: int = 10,
        bind_images_dir: bool = False,
        docker_compose_version: str = "3.9",
        verbose: bool = True,
        enable_ssl: bool = False,
        email: str = "user@example.com",
        install_syntax_highlighting: bool = False,
    ):

   
        self.output_dir = output_dir
        self.project_name = project_name
        self.db_image = db_image
        self.mw_image = mw_image
        self.mw_http_port = mw_http_port
        self.db_port = db_port
        self.mw_dbname = mw_dbname
        self.mw_dbuser = mw_dbuser
        self.mw_dbpass = mw_dbpass
        self.mw_rootpass = mw_rootpass
        self.mw_admin_user = mw_admin_user
        self.mw_admin_pass = mw_admin_pass
        self.mw_site_name = mw_site_name
        self.mw_site_lang = mw_site_lang
        self.mw_server = mw_server
        self.mw_extensions = mw_extensions or []
        self.mw_skins = mw_skins or ["vector"]
        self.enable_autoimport = enable_autoimport
        self.autoimport_marker = autoimport_marker
        self.syntax_config = syntax_config or SyntaxHighlightConfig()
        self.python_injector_script = python_injector_script
        self.injector_mount_path = injector_mount_path
        self.wiki_logo_path = wiki_logo_path
        self.auto_import_xml = auto_import_xml
        self.docker_volume_name = docker_volume_name
        self.php_modules = php_modules or [
            "memory_limit=1024M",
            "max_execution_time=0",
        ]
        self.sleep_time = sleep_time
        self.bind_images_dir = bind_images_dir
        self.docker_compose_version = docker_compose_version
        self.verbose = verbose
        self.email = email
        self.install_syntax_highlighting = install_syntax_highlighting
        self.enable_ssl = enable_ssl


    # -------------------------------------------------------------------------
    def _generate_php_config_lines(self) -> str:
        """Render PHP configuration lines for container."""
        lines = []
        bOnce = False
        for kv in self.php_modules:
            key, value = kv.split("=", 1)
            filename = key.replace(".", "_")
            if not bOnce:
                lines.append(
                    f'echo "{key} = {value}" > /usr/local/etc/php/conf.d/{filename}.ini;'
                )
            else:
                lines.append(
                    f'    echo "{key} = {value}" > /usr/local/etc/php/conf.d/{filename}.ini;'
                )
            bOnce = True
        # Use 12 spaces of indentation to match the rest of the shell block
        return "\n            ".join(lines)


    # -------------------------------------------------------------------------
    def _generate_extension_loads(self) -> str:
        """Render wfLoadExtension calls for LocalSettings.php."""
        lines = []
        # Always include the syntax highlighter extension first
        lines.append(
            f'echo "wfLoadExtension( \'\\\'\'{self.syntax_config.extension}\'\\\'\' );" >> /var/www/html/LocalSettings.php;'
        )
        for ext in self.mw_extensions:
            lines.append(
                f'echo "wfLoadExtension( \'\\\'\'{ext}\\\'\' );" >> /var/www/html/LocalSettings.php;'
            )
        return "\n          ".join(lines)


    # -------------------------------------------------------------------------
    def _generate_skin_config(self) -> str:
        """Render skin configuration for LocalSettings.php."""
        default_skin = self.mw_skins[0] if self.mw_skins else "vector"
        return (
            f'echo "\\$$wgDefaultSkin = \'"\'"\'{default_skin}\'"\'"\' ;" >> /var/www/html/LocalSettings.php;'
        )

    def _generate_logo_config(self) -> str:
        """Render logo configuration for LocalSettings.php."""
        return (
            'echo "\\$$wgLogos = [\'"\'"\'icon\'"\'"\' => \'"\'"\'$$wgScriptPath/resources/assets/wiki_custom_logo.png\'"\'"\''
            ', \'"\'"\'1x\'"\'"\' => \'"\'"\'$$wgScriptPath/resources/assets/wiki_custom_logo.png\'"\'"\''
            '];" >> /var/www/html/LocalSettings.php;'
        )


    # -------------------------------------------------------------------------
    def generate(self) -> str:
        """Generate the docker-compose.yml content as a string."""
        php_conf = self._generate_php_config_lines()
        ext_loads = self._generate_extension_loads()
        skin_conf = self._generate_skin_config()
        logo_conf = self._generate_logo_config()

        transportServerPrepend = 'https://' if self.enable_ssl else 'http://'

        autoRunXML = './AutoFirstRunImport.xml'

        images_mount = (
            "- ./images:/var/www/html/images" if self.bind_images_dir else "#- ./images:/var/www/html/images"
        )

        autoimport_block = textwrap.dedent(
            f"""echo "Contemplating auto import";
        if [ -s /var/www/html/AutoFirstRunImport.xml ] && [ {str(self.enable_autoimport).lower()} = true ]; then
          echo "📦 Found AutoFirstRunImport.xml — beginning import...";
          php maintenance/importDump.php --conf /var/www/html/LocalSettings.php --username-prefix="" /var/www/html/AutoFirstRunImport.xml;
          echo "🔁 Rebuilding site statistics...";
          php maintenance/initSiteStats.php --update;
          touch {self.autoimport_marker}
        else
          echo "🕳️ Auto import disabled or no file found.";
        fi;
            """
        ).strip()

        # Re-indent it for YAML’s command block (12 spaces typical)
        autoimport_block = textwrap.indent(autoimport_block, "            ")


        install_syntax_highlighting_consequencestring = (
            textwrap.dedent(f"""
                echo "Hypothecating lexer...";
                                  python3 {self.injector_mount_path} &
            """).strip()
            if self.install_syntax_highlighting else ""
        )

        install_syntax_highlighting_rereg_consequencestring = (
            textwrap.dedent(f"""
                echo "Reregistering lexer...";
                                  python3 {self.injector_mount_path} --rereg &
            """).strip()
            if self.install_syntax_highlighting else ""
        )

        compose_text = textwrap.dedent(f"""
        
        services:
          papyrusproj_{self.project_name}_mediawiki_unattended_db:
            image: {self.db_image}
            restart: always
            environment:
              MYSQL_DATABASE: {self.mw_dbname}
              MYSQL_USER: {self.mw_dbuser}
              MYSQL_PASSWORD: {self.mw_dbpass}
              MYSQL_ROOT_PASSWORD: {self.mw_rootpass}
            volumes:
              - {self.docker_volume_name}:/var/lib/mysql
            ports:
              - "{self.db_port}:3306"

          papyrusproj_{self.project_name}_mediawiki_unattended_wikiserver:
            image: {self.mw_image}
            restart: always
            ports:
              - "{self.mw_http_port}:80"
            environment:
              MW_DBTYPE: mysql
              MW_DBHOST: mediawiki_unattended_db
              MW_DBNAME: {self.mw_dbname}
              MW_DBUSER: {self.mw_dbuser}
              MW_DBPASS: {self.mw_dbpass}
              MW_SITE_NAME: "{self.mw_site_name}"
              MW_SITE_LANG: {self.mw_site_lang}
              MW_SERVER: "{transportServerPrepend}{self.mw_server}"
              MW_ADMIN_USER: {self.mw_admin_user}
              MW_ADMIN_PASS: {self.mw_admin_pass}
            volumes:
            {images_mount}
              - {self.python_injector_script}:{self.injector_mount_path}
              - {self.wiki_logo_path}:/var/www/html/resources/assets/wiki_custom_logo.png
              - {autoRunXML}:/var/www/html/AutoFirstRunImport.xml
            command: |
              /bin/bash -c '
                echo "⏳ Waiting {self.sleep_time} seconds for MariaDB to settle...";
                sleep {self.sleep_time};
                echo "🧠 Configuring PHP settings...";
                {php_conf}

                if [ ! -f /var/www/html/LocalSettings.php ]; then
                  echo "⚙️ Running unattended MediaWiki installation...";
                  php maintenance/run.php install \\
                    --dbname={self.mw_dbname} \\
                    --dbtype=mysql \\
                    --dbserver=papyrusproj_{self.project_name}_mediawiki_unattended_db \\
                    --dbport=3306 \\
                    --dbuser={self.mw_dbuser} \\
                    --dbpass={self.mw_dbpass} \\
                    --installdbuser={self.mw_dbuser} \\
                    --installdbpass={self.mw_dbpass} \\
                    --server={transportServerPrepend}{self.mw_server} \\
                    --scriptpath="" \\
                    --lang={self.mw_site_lang} \\
                    --pass={self.mw_admin_pass} \\
                    "{self.mw_site_name}" {self.mw_admin_user};

                  {install_syntax_highlighting_consequencestring}

                  echo "🔌 Enabling {self.syntax_config.extension}...";
                  {ext_loads}

                  echo "🎨 Configuring logo...";
                  {logo_conf}

                  echo "🎨 Applying default skin...";
                  {skin_conf}

                  {autoimport_block}
                  {install_syntax_highlighting_rereg_consequencestring}
                else
                  echo "✅ LocalSettings.php already exists — skipping installation.";
                fi;
                exec apache2-foreground
              '

        volumes:
          {self.docker_volume_name}:
        """).rstrip() + "\n"


        if not compose_text.endswith("\r\n"):
            compose_text += "\r\n"

        return compose_text

    def write_ssl_service_addendum(self, compose_text: str) -> str:
        """
        Inject a Caddy reverse proxy SSL service into the generated docker-compose YAML,
        append corresponding caddy volumes, and generate the Caddyfile.

        Args:
            compose_text (str): The base docker-compose YAML string.

        Returns:
            str: Modified docker-compose YAML with Caddy SSL support.
        """

        # Define the add-on YAML and volumes (aligned correctly under 'services:')
        caddy_service = textwrap.dedent(
            f"""
            papyrusproj_{self.project_name}_caddy:
                image: caddy:2
                restart: always
                depends_on:
                - papyrusproj_{self.project_name}_mediawiki_unattended_wikiserver
                ports:
                - "80:80"
                - "443:443"
                volumes:
                - ./Caddyfile:/etc/caddy/Caddyfile
                - caddy_data:/data
                - caddy_config:/config
            """
        ).rstrip()

        # Inject the service block before the first top-level 'volumes:' section if it exists
        if "\nvolumes:" in compose_text:
            modified = compose_text.replace(
                "\nvolumes:",
                f"\n{caddy_service}\n\nvolumes:",
                1
            )
        else:
            # Fallback append if volumes section missing
            modified = compose_text.rstrip() + f"\n{caddy_service}\n"

        # Append the caddy volumes at the end (aligned at top-level)
        modified = modified.rstrip() + textwrap.dedent(
            """

            caddy_data:
            caddy_config:
            """
        )

        # Write the Caddyfile with appropriate TLS configuration
        caddyfile_path = os.path.join(self.output_dir, "Caddyfile")
        os.makedirs(self.output_dir, exist_ok=True)

        # Choose TLS mode based on provided email
        if getattr(self, "email", None) and "example.com" not in self.email.lower():
            tls_line = f"tls {self.email}"
            mode = "public ACME (Let's Encrypt)"
        else:
            tls_line = "tls internal"
            mode = "local self-signed (internal CA)"

        caddyfile_content = textwrap.dedent(f"""\
            :80 {{
                redir https://{{{{host}}}}:443{{{{uri}}}}
            }}

            :443 {{
                {tls_line}
                reverse_proxy papyrusproj_{self.project_name}_mediawiki_unattended_wikiserver:80
            }}
        """)

        with open(caddyfile_path, "w", encoding="utf-8") as f:
            f.write(caddyfile_content)

        if self.verbose:
            print(f"[🔐] SSL enabled ({mode}): Caddyfile written to {caddyfile_path}")

        return modified




    # -------------------------------------------------------------------------

    def write(self, filename: str = "docker-compose.yml") -> str:
        """Write the docker-compose.yml to disk."""
        os.makedirs(self.output_dir, exist_ok=True)

        output_path = os.path.join(self.output_dir, filename)

        compose_text = self.generate()

        # Let SSL handler modify it if needed
        if getattr(self, "enable_ssl", False):
            compose_text = self.write_ssl_service_addendum(compose_text)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(compose_text)

        if self.verbose:
            print(f"[🧱] Docker Compose written to {output_path}")
        return output_path



def ensure_auto_import_xml(output_xml_path: str, autoimport_target: str):
    """Ensure the generated XML is duplicated or symlinked to the autoimport location."""
    if not os.path.exists(output_xml_path):
        print(f"[⚠️] No output XML found at {output_xml_path}; skipping autoimport copy.")
        return
    os.makedirs(os.path.dirname(autoimport_target), exist_ok=True)
    if os.path.exists(autoimport_target):
        os.remove(autoimport_target)
    shutil.copy2(output_xml_path, autoimport_target)
    print(f"[📦] Copied {output_xml_path} → {autoimport_target} for auto-import.")




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
    def __init__(self, name: str, extends: str, flags: Optional[List[str]] = None):
        self.name = name
        self.extends = extends
        self.properties: List[PapyrusProperty] = []
        self.functions: List[PapyrusFunction] = []
        self.events: List[PapyrusEvent] = []
        self.structs: List[PapyrusStruct] = []
        self.flags: List[str] = []


    def to_mediawiki(self) -> str:
        out = [
            f"'''Extends:''' [[{self.extends} Script]]",
            "",
            f"Script for manipulating {self.name} instances.",
            "",
        ]
        out.append("== Definition ==")
        out.append("<syntaxhighlight lang=\"papyrus\">")
        if self.flags and len(self.flags) > 0:
            flagsListString = ' '.join(self.flags)
            out.append(f"ScriptName {self.name} extends {self.extends} {flagsListString}")
        else:
            out.append(f"ScriptName {self.name} extends {self.extends}")
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

    Optional batching mode:
      enable_batch=True -> cache writes and flush in bulk
      batch_id -> logical grouping tag (for logging or partitioning)
    """

    def __init__(
        self,
        conn: Union[str, Path, sqlite3.Connection],
        dialect: str = "sqlite",
        schema: Optional[str] = None,
        autocommit: bool = True,  # May thrash writes but prevent schema out-of-order linking problems.
        quash_errors: bool = True,
        enable_batch: bool = False,
        batch_id: Optional[str] = None,
        batch_size: int = 1000,
    ):
        self.dialect = dialect.lower()
        self.schema = schema
        self.autocommit = autocommit
        self.quash_errors = quash_errors
        self.enable_batch = enable_batch
        self.batch_id = batch_id
        self.batch_size = batch_size

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

        # --- batch buffers ---
        self._batch_buffers = {
            "scripts": [],
            "functions": [],
            "events": [],
            "misc_pages": [],
        }

    # -------------------------------------------------------------------------
    # SCHEMA SETUP
    # -------------------------------------------------------------------------

    def _ensure_schema(self):
        """Create base tables for Papyrus documentation, in a cross-dialect-safe way."""
        if self.dialect == "sqlite":
            prefix = ""
            id_type = "INTEGER PRIMARY KEY AUTOINCREMENT"
        elif self.dialect.startswith("post"):
            prefix = f"{self.schema}." if self.schema else ""
            id_type = "SERIAL PRIMARY KEY"
            # Ensure schema exists before creating tables
            if self.schema:
                self.cur.execute(f"CREATE SCHEMA IF NOT EXISTS {self.schema};")
        else:
            raise ValueError(f"Unsupported dialect: {self.dialect}")

        ddl_statements = [
            f"""
            CREATE TABLE IF NOT EXISTS {prefix}scripts (
                id {id_type},
                name TEXT NOT NULL,
                extends TEXT,
                summary TEXT
            );
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {prefix}functions (
                id {id_type},
                script_name TEXT NOT NULL,
                name TEXT NOT NULL,
                return_type TEXT,
                params TEXT,
                flags TEXT,
                description TEXT
            );
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {prefix}events (
                id {id_type},
                script_name TEXT NOT NULL,
                name TEXT NOT NULL,
                params TEXT,
                description TEXT
            );
            """,
            f"""
            CREATE TABLE IF NOT EXISTS {prefix}misc_pages (
                id {id_type},
                title TEXT NOT NULL,
                content TEXT
            );
            """,
        ]

        for stmt in ddl_statements:
            self.cur.execute(stmt)

        if self.autocommit:
            self.conn.commit()

    # -------------------------------------------------------------------------
    # INTERNAL EXECUTION HELPERS
    # -------------------------------------------------------------------------

    def _execute_safe(self, query: str, params: tuple):
        """Execute a query and rollback if necessary."""
        try:
            self.cur.execute(query, params)
            if self.autocommit:
                self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise RuntimeError(f"SQLDocSink query failed: {e}") from e

    def _batch_append(self, table: str, row: tuple):
        """Append a row to a batch buffer, flushing if over threshold."""
        buf = self._batch_buffers[table]
        buf.append(row)
        if len(buf) >= self.batch_size:
            self._flush_table(table)

    def _flush_table(self, table: str):
        """Flush one table’s buffer using executemany."""
        buf = self._batch_buffers[table]
        if not buf:
            return

        if table == "scripts":
            query = (
                "INSERT INTO scripts (name, extends, summary) VALUES (?, ?, ?)"
                if self.dialect == "sqlite"
                else "INSERT INTO scripts (name, extends, summary) VALUES (%s, %s, %s)"
            )
        elif table == "functions":
            query = (
                "INSERT INTO functions (script_name, name, return_type, params, flags, description) VALUES (?, ?, ?, ?, ?, ?)"
                if self.dialect == "sqlite"
                else "INSERT INTO functions (script_name, name, return_type, params, flags, description) VALUES (%s, %s, %s, %s, %s, %s)"
            )
        elif table == "events":
            query = (
                "INSERT INTO events (script_name, name, params, description) VALUES (?, ?, ?, ?)"
                if self.dialect == "sqlite"
                else "INSERT INTO events (script_name, name, params, description) VALUES (%s, %s, %s, %s)"
            )
        elif table == "misc_pages":
            query = (
                "INSERT INTO misc_pages (title, content) VALUES (?, ?)"
                if self.dialect == "sqlite"
                else "INSERT INTO misc_pages (title, content) VALUES (%s, %s)"
            )
        else:
            raise ValueError(f"Unknown table for batch flush: {table}")

        try:
            self.cur.executemany(query, buf)
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise RuntimeError(f"SQLDocSink batch flush failed for {table}: {e}") from e
        finally:
            buf.clear()

    def flush_all(self):
        """Flush all pending batch buffers."""
        for table in self._batch_buffers.keys():
            self._flush_table(table)

    # -------------------------------------------------------------------------
    # PUBLIC WRITE METHODS
    # -------------------------------------------------------------------------

    def write_misc(self, title: str, text: str):
        row = (title, text)
        if self.enable_batch:
            self._batch_append("misc_pages", row)
        else:
            self._execute_safe(
                "INSERT INTO misc_pages (title, content) VALUES (?, ?)"
                if self.dialect == "sqlite"
                else "INSERT INTO misc_pages (title, content) VALUES (%s, %s)",
                row,
            )

    def write_script(self, script: "PapyrusScript"):
        row = (
            script.name,
            script.extends,
            f"{len(script.functions)} funcs, {len(script.events)} events",
        )
        if self.enable_batch:
            self._batch_append("scripts", row)
        else:
            self._execute_safe(
                "INSERT INTO scripts (name, extends, summary) VALUES (?, ?, ?)"
                if self.dialect == "sqlite"
                else "INSERT INTO scripts (name, extends, summary) VALUES (%s, %s, %s)",
                row,
            )

    def write_function(self, script_name: str, fn: "PapyrusFunction"):
        row = (
            script_name,
            fn.name,
            fn.return_type,
            fn.params,
            fn.flags,
            fn.description,
        )
        if self.enable_batch:
            self._batch_append("functions", row)
        else:
            self._execute_safe(
                "INSERT INTO functions (script_name, name, return_type, params, flags, description) VALUES (?, ?, ?, ?, ?, ?)"
                if self.dialect == "sqlite"
                else "INSERT INTO functions (script_name, name, return_type, params, flags, description) VALUES (%s, %s, %s, %s, %s, %s)",
                row,
            )

    def write_event(self, script_name: str, ev: "PapyrusEvent"):
        row = (script_name, ev.name, ev.params, ev.description)
        if self.enable_batch:
            self._batch_append("events", row)
        else:
            self._execute_safe(
                "INSERT INTO events (script_name, name, params, description) VALUES (?, ?, ?, ?)"
                if self.dialect == "sqlite"
                else "INSERT INTO events (script_name, name, params, description) VALUES (%s, %s, %s, %s)",
                row,
            )

    # -------------------------------------------------------------------------
    # FINALIZATION
    # -------------------------------------------------------------------------

    def finalize(self):
        """Safely flush, commit, and close all SQL resources."""
        commit_err = None

        try:
            if self.enable_batch:
                self.flush_all()
            self.conn.commit()
        except Exception as e:
            commit_err = e
            if not self.quash_errors:
                raise RuntimeError(f"Finalize failed during commit: {e}") from e

        try:
            if self.cur:
                self.cur.close()
        except Exception as e:
            if not self.quash_errors:
                raise RuntimeError(f"Finalize failed while closing cursor: {e}") from e

        try:
            if self.conn:
                self.conn.close()
        except Exception as e:
            if not self.quash_errors:
                raise RuntimeError(f"Finalize failed while closing connection: {e}") from e

        if commit_err and self.quash_errors:
            import sys
            print(f"[SQLDocSink] Warning: commit failed during finalize: {commit_err}", file=sys.stderr)





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
    # old trusty version without flags
    # SCRIPT_PATTERN = re.compile(r"ScriptName\s+(?P<name>[A-Za-z0-9_:#]+)(\s+extends\s+(?P<extends>[A-Za-z0-9_:#]+))?", re.IGNORECASE)
    SCRIPT_PATTERN = re.compile(
        r"ScriptName\s+(?P<name>[A-Za-z0-9_:#]+)"
        r"(?:\s+extends\s+(?P<extends>[A-Za-z0-9_:#]+))?"
        r"(?:\s+(?P<flags>(?:native|hidden|sealed|conditional|global|abstract|final|\s+)*))?",
        re.IGNORECASE,
    )
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
                flags = m.group("flags") or ""
                flags_list = [f.strip().capitalize() for f in flags.split() if f.strip()] # we don't *need* to case normalize
                script = PapyrusScript(script_name, extends, flags=flags_list)
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
    Updated impl of the Papyrus .pex → .psc automation.
    - Validates paths
    - Supports Wine, Bottles, and Proton (with 'proton run')
    - Prevents accidental overwrites
    - Adds timeouts, sandboxing, and clean environment
    """

    def __init__(
        self,
        decompiler_path: str,
        force: bool = False,
        runner_hint: Optional[str] = None,
        env: Optional[dict] = None,
        timeout: int = 60,
        base_dir: Optional[str] = None,
        sandbox: bool = True,
    ):
        """
        :param decompiler_path: Path to the decompiler executable.
        :param force: Re-decompile even if PSC is newer than PEX.
        :param runner_hint: e.g. "wine", "wine64", "bottles-cli run", or "proton".
        :param env: Optional environment vars to merge into safe environment.
        :param timeout: Kill subprocess after N seconds.
        :param base_dir: Restrict file I/O to this directory.
        :param sandbox: Use firejail (if available) for filesystem isolation.
        """
        self.decompiler_path = Path(decompiler_path).resolve()
        self.force = force
        self.timeout = timeout
        self.base_dir = Path(base_dir or os.getcwd()).resolve()
        self.env = self._make_safe_env(env)
        self.runner_hint = runner_hint
        self.is_windows = platform.system().lower().startswith("win")
        self.sandbox = sandbox
        self.runner = self._detect_runner()

        if not self.decompiler_path.exists():
            raise FileNotFoundError(f"Decompiler not found: {self.decompiler_path}")

        print(f"🧱 Using decompiler: {self.decompiler_path}")
        print(f"🔒 Sandbox: {'on' if self.sandbox else 'off'} | Timeout: {self.timeout}s")

    # ---------------------------------------------------------------------- #
    #  Environment and runner detection
    # ---------------------------------------------------------------------- #
    def _make_safe_env(self, user_env: Optional[dict]) -> dict:
        safe_env = {
            "PATH": os.getenv("PATH", ""),
            "HOME": os.getenv("HOME", "/tmp"),
            "LANG": os.getenv("LANG", "C.UTF-8"),
        }
        if user_env:
            safe_env.update(user_env)
        return safe_env

    def _detect_runner(self) -> Optional[List[str]]:
        """Detect execution environment (native, wine, proton, bottles)."""
        if self.is_windows:
            return None

        # explicit user hint
        if self.runner_hint:
            parts = self.runner_hint.split()
            if shutil.which(parts[0]):
                return parts
            raise RuntimeError(f"Runner '{self.runner_hint}' not found in PATH.")

        # auto-detect
        for candidate in ("wine64", "wine", "bottles-cli", "proton"):
            if shutil.which(candidate):
                print(f"🔧 Found runner: {candidate}")
                return [candidate]
        return None

    # ---------------------------------------------------------------------- #
    #  Utility and validation helpers
    # ---------------------------------------------------------------------- #
    def _within_base_dir(self, path: Path) -> bool:
        try:
            return self.base_dir in path.resolve().parents
        except Exception:
            return False

    def _should_skip(self, pex: Path, psc: Path) -> bool:
        if self.force:
            return False
        return psc.exists() and psc.stat().st_mtime > pex.stat().st_mtime

    # ---------------------------------------------------------------------- #
    #  Command builder
    # ---------------------------------------------------------------------- #
    def _build_command(self, pex: Path) -> List[str]:
        exe = str(self.decompiler_path)
        args = [exe, str(pex)]

        if not self.runner:
            return args

        runner = self.runner[0]

        if runner == "proton":
            # Proton needs "proton run ..."
            compat_dir = os.path.join(tempfile.gettempdir(), "proton-sandbox")
            os.makedirs(compat_dir, exist_ok=True)
            self.env.setdefault("STEAM_COMPAT_DATA_PATH", compat_dir)
            return ["proton", "run"] + args
        elif runner == "bottles-cli":
            return ["bottles-cli", "run", exe, str(pex)]
        else:
            # e.g. wine, wine64
            return [runner, exe, str(pex)]

    # ---------------------------------------------------------------------- #
    #  Decompile one file
    # ---------------------------------------------------------------------- #
    def _decompile_one(self, pex: Path) -> Optional[Path]:
        if not self._within_base_dir(pex):
            print(f"⚠️ Skipping {pex}: outside base directory")
            return None

        expected_psc = pex.with_suffix(".psc")
        if self._should_skip(pex, expected_psc):
            print(f"⏩ Skipping {pex.name} (already decompiled)")
            return expected_psc

        print(f"🧩 Decompiling {pex.name}...")

        cmd = self._build_command(pex)

        # firejail sandbox if available
        if self.sandbox and shutil.which("firejail"):
            cmd = ["firejail", "--quiet", "--private=" + str(self.base_dir)] + cmd

        temp_psc = expected_psc.with_suffix(".psc.tmp")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=self.env,
                timeout=self.timeout,
                check=False,
                cwd=str(self.base_dir),
            )
        except subprocess.TimeoutExpired:
            print(f"⏰ Timeout while decompiling {pex.name}")
            return None
        except Exception as e:
            print(f"❌ Execution failed for {pex.name}: {e}")
            return None

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            print(f"⚠️ Decompiler error ({pex.name}): {stderr or stdout}")
            return None

        # Check for result file
        if expected_psc.exists():
            print(f"✅ Decompiled → {expected_psc}")
            return expected_psc
        elif temp_psc.exists():
            temp_psc.rename(expected_psc)
            print(f"✅ Moved temp output → {expected_psc}")
            return expected_psc
        else:
            print(f"⚠️ Expected output missing: {expected_psc}")
            return None

    # ---------------------------------------------------------------------- #
    #  File discovery and execution
    # ---------------------------------------------------------------------- #
    def find_pex_files(self, directory: str) -> List[Path]:
        root = Path(directory).resolve()
        if not self._within_base_dir(root):
            raise PermissionError(f"{root} is outside base dir {self.base_dir}")
        return sorted(root.rglob("*.pex"))

    def run(self, directory: str) -> List[Path]:
        print(f"🔍 Searching for .pex files under {directory}")
        pex_files = self.find_pex_files(directory)
        if not pex_files:
            print("ℹ️ No .pex files found.")
            return []

        generated = []
        for pex in pex_files:
            psc = self._decompile_one(pex)
            if psc:
                generated.append(psc)

        print(f"✅ Decompilation complete. {len(generated)} .psc files ready.")
        return generated



if __name__ == "__main__":
    import argparse
    import traceback
 
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
    ap.add_argument("--domain", help="Domain for HTTPS setup (required if --ssl is used)", default="localhost",)
    ap.add_argument("--email", help="Email for Let's Encrypt SSL")
    #ap.add_argument("--local-ssl", action="store_true", help="Use local/internal certs")
    ap.add_argument("--db", action="store_true", help="Include database container in docker-compose")

    ap.add_argument("--wiki-user", default="ReedPapyri", help="Contributor username for XML exports")
    ap.add_argument("--wiki-name", default="Papyrus Docs Wiki", help="Wiki name that appears to users in search box")
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

    ap.add_argument(
        "--no-autoimport-copy",
        action="store_true",
        help="Skip copying the generated XML to AutoFirstRunImport.xml for Docker auto-import."
    )

    ap.add_argument(
    "--init-wikibuildcontext",
    action="store_true",
    help="Generate missing wiki build context files (papyruslexerconjecture.py and wiki.png) in the output directory after Docker warnings.",
    )

    ap.add_argument(
        "--dockerport-randomize",
        action="store_true",
        help="Randomize MediaWiki and database host ports to help avoid collisions when running multiple wikis."
    )
    ap.add_argument(
        "--dockerport-portmw",
        type=int,
        default=40201,
        help="Host port to expose the MediaWiki HTTP service (default: 40201)."
    )
    ap.add_argument(
        "--dockerport-portdb",
        type=int,
        default=30433,
        help="Host port to expose the MariaDB service (default: 30433)."
    )

    ap.add_argument("--sqlsink-enable-batch", action="store_true", help="Enable batch write mode.")
    ap.add_argument("--sqlsink-batch-id", type=str, help="Logical batch ID for this run.")
    ap.add_argument("--sqlsink-batch-size", type=int, default=500, help="Flush size for batched writes.")

    ap.add_argument(
        "--docker-wikilogo",
        type=str,
        help="Path to a custom PNG logo for the Docker MediaWiki build. "
            "If omitted, a default dummy logo will be used."
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
            # Initialize the SQL sink with batching options from CLI.
            # Note: when batching is enabled we disable autocommit for efficiency.
            sink = SQLDocSink(
                conn=args.db_conn,
                dialect=args.db_dialect,
                autocommit=not args.sqlsink_enable_batch,
                enable_batch=args.sqlsink_enable_batch,
                batch_id=args.sqlsink_batch_id,
                batch_size=args.sqlsink_batch_size,
            )

            # Basic connection sanity check.
            try:
                sink.cur.execute("SELECT 1;")
                sink.conn.commit()
            except Exception as e:
                # Close resources before exiting to avoid leaking handles.
                try:
                    sink.finalize()
                except Exception:
                    pass
                sys.exit(f"❌ Database connection test failed: {type(e).__name__}: {e}")
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
    archive_name = 'PapyrusRef'
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


                xml_path = output_file #os.path.join(output_dir, "PapyrusDocs.xml")
                auto_import_xml = output_dir / "AutoFirstRunImport.xml"


                if not args.no_autoimport_copy:
                    ensure_auto_import_xml(xml_path, auto_import_xml)

                if args.ssl and not args.domain:
                    print("⚠️ SSL requested but no domain provided — skipping Caddy setup.")

                if not args.domain:
                    args.domain = 'localhost'

                autoisolate_volprefix_base_name = args.project_name or "pscproj"
                #autoisolate_volprefix_base_name = os.path.basename(os.path.abspath(args.out)) or "pscproj"
                autoisolate_volprefix_volume_name = f"papyrus_{autoisolate_volprefix_base_name}_db_data"


                # Handle port randomization or overrides
                if args.dockerport_randomize:
                    import random
                    # Add a random offset in a reasonable range (so they don’t collide)
                    offset = random.randint(0, 499)
                    mw_port = args.dockerport_portmw + offset
                    db_port = args.dockerport_portdb + offset
                    print(f"🎲 Randomizing Docker ports → MediaWiki:{mw_port}  MariaDB:{db_port}")
                else:
                    mw_port = args.dockerport_portmw
                    db_port = args.dockerport_portdb

                docker_gen = PapyrusDockerComposeUnattendedSQLDatabaseVersion(
                    project_name=args.project_name,
                    output_dir=args.out,
                    enable_ssl=args.ssl,
                    mw_server= args.domain+":"+str(mw_port) if args.domain == 'localhost' else args.domain,
                    email=args.email,
                    #local_ssl=args.local_ssl,
                    install_syntax_highlighting=args.install_syntax_highlighting,
                    auto_import_xml=auto_import_xml,
                    docker_volume_name=autoisolate_volprefix_volume_name,
                    db_port=db_port,
                    mw_http_port=mw_port,
                    mw_site_name=args.wiki_name
                ).write()



                missing = []
                expected_files = {
                    "Papyrus lexer injector": Path("papyruslexerconjecture.py"),
                    "Wiki logo": Path(output_dir) / "wiki.png",
                    "Auto import XML": auto_import_xml,
                }

                for label, path in expected_files.items():
                    if not path.exists():
                        missing.append(f"  - {label}: {path}")

                if missing:
                    print("⚠️  WARNING: The following required files are missing in this directory:")
                    for item in missing:
                        print(item)
                    print("")
                    print("Docker will still run, but the wiki may not build or render properly.")
                    print("You can pass --init-wikibuildcontext to generate stub assets.")
                    print("Ensure the files above exist relative to the compose file before running:")
                    print("   docker compose up")
                    print("")


                if args.init_wikibuildcontext:
                    print("🧩 Initializing wiki build context...")

                    try:
                        injector_path = Path(output_dir) / "papyruslexerconjecture.py"
                        if not injector_path.exists():
                            print(f"⚙️ Generating Papyrus lexer injector → {injector_path}")
                            
                            # ✅ instantiate the class properly
                            injector = PapyrusLexerInjectorGenerator(injector_path)
                            injector.write()
                            
                            print(f"✅ Wrote {injector_path}")
                        else:
                            print(f"✔ Lexer injector already exists at {injector_path}")
                    except Exception as e:
                        print(f"⚠️ Failed to generate injector: {e}")


                    # 2. Handle wiki logo
                    try:
                        wiki_png_path = Path(output_dir) / "wiki.png"

                        if args.docker_wikilogo and Path(args.docker_wikilogo).is_file():
                            try:
                                with open(args.docker_wikilogo, "rb") as f:
                                    magic = f.read(8)
                                if magic == b"\x89PNG\r\n\x1a\n":
                                    shutil.copy2(args.docker_wikilogo, wiki_png_path)
                                    print(f"🖼️ Copied custom wiki logo → {wiki_png_path}")
                                else:
                                    print(f"⚠️ Custom logo '{args.docker_wikilogo}' is not a valid PNG (magic mismatch). Generating dummy logo instead.")
                                    ensure_dummy_png(wiki_png_path, color=(255, 255, 255, 255), size=(160, 160))
                            except Exception as e:
                                print(f"⚠️ Failed to verify logo file: {e}. Generating dummy logo instead.")
                                ensure_dummy_png(wiki_png_path, color=(255, 255, 255, 255), size=(160, 160))
                        else:
                            # Fallback to dummy
                            ensure_dummy_png(wiki_png_path, color=(255, 255, 255, 255), size=(160, 160))
                            if args.docker_wikilogo:
                                print(f"⚠️ Custom logo not found at {args.docker_wikilogo}, generated dummy instead.")
                            else:
                                print("✔ No custom logo specified; generated dummy PNG.")

                    except Exception as e:
                        print(f"⚠️ Failed to prepare wiki logo: {e}")

                    print("🎉 Wiki build context initialized successfully.")



                # --- User guidance about Docker usage --------------------------------
                print("🧩  Docker usage note:")
                print("   - To start the environment in the foreground (recommended for first run):")
                print("       docker compose up")
                print("   - To detach and run in the background (optional):")
                print("       docker compose up -d")
                print("")
                print("💣  If you wish to completely reset your MediaWiki installation state")
                print("    and destroy all volume data, use:")
                print("       docker compose down -v")
                print("    (This will wipe all wiki content, users, and the MariaDB volume.)")
                print("")



            except Exception as e:
                print(f"⚠️ Docker generation failed: {e}")


    print(f"✅ Completed: {total_scripts} Papyrus scripts processed in mode '{args.mode}'.")
    print("🎆 Done.")




