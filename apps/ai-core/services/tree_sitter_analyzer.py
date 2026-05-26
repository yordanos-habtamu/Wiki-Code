import os
import sys
import traceback

try:
    from tree_sitter import Language, Parser
    import tree_sitter_python as tspython
    import tree_sitter_go as tsgo
    import tree_sitter_php as tsphp
except ImportError:
    Language = None
    Parser = None
    tspython = None
    tsgo = None
    tsphp = None

SUPPORTED_EXTENSIONS = {
    '.py': 'python',
    '.go': 'go',
    '.php': 'php'
}

PUBLIC_SYMBOL_TYPES = {
    'python': {'function_definition', 'class_definition'},
    'go': {'function_declaration', 'method_declaration', 'type_spec'},
    'php': {'function_definition', 'class_declaration', 'interface_declaration', 'trait_declaration'}
}

IMPORT_NODE_TYPES = {
    'python': {'import_statement', 'import_from_statement'},
    'go': {'import_spec'},
    'php': {'namespace_use_declaration', 'use_statement'}
}

LANGUAGE_MODULES = {
    'python': tspython,
    'go': tsgo,
    'php': tsphp
}


class LanguageRouter:
    def __init__(self):
        self.parsers = {}
        self._initialize_parsers()

    def _initialize_parsers(self):
        if Parser is None:
            print('[LanguageRouter] tree-sitter not installed, analyzer disabled', file=sys.stderr)
            return

        for extension, language in SUPPORTED_EXTENSIONS.items():
            module = LANGUAGE_MODULES.get(language)
            if module is None:
                continue
            try:
                capsule = None
                if hasattr(module, 'language'):
                    capsule = module.language()
                elif hasattr(module, 'language_php'):
                    capsule = module.language_php()
                elif hasattr(module, 'language_go'):
                    capsule = module.language_go()
                else:
                    print(f'[LanguageRouter] Unsupported language module for {extension}', file=sys.stderr)
                    continue

                if capsule is None:
                    raise RuntimeError('Failed to obtain tree-sitter language capsule')

                language_obj = Language(capsule)
                parser = Parser()
                parser.language = language_obj
                self.parsers[extension] = parser
            except Exception as exc:
                print(f'[LanguageRouter] Failed to initialize parser for {extension}: {exc}', file=sys.stderr)
                traceback.print_exc(file=sys.stderr)

    def supported_extensions(self):
        return set(self.parsers.keys())

    def analyze_file(self, file_path):
        extension = os.path.splitext(file_path)[1].lower()
        result = {
            'file_path': file_path,
            'symbols': [],
            'imports': []
        }

        if Parser is None or extension not in self.parsers:
            return result

        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                contents = f.read()
            parser = self.parsers[extension]
            tree = parser.parse(bytes(contents, 'utf8'))
            return self._extract_symbols_and_imports(tree, contents, extension, file_path)
        except Exception as exc:
            print(f'[LanguageRouter] Failed to analyze {file_path}: {exc}', file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return result

    def _extract_symbols_and_imports(self, tree, contents, extension, file_path):
        symbols = []
        imports = []
        language = SUPPORTED_EXTENSIONS.get(extension, extension)

        for node in self._traverse(tree.root_node):
            if node.type in PUBLIC_SYMBOL_TYPES.get(language, set()):
                symbol = self._extract_symbol(node, contents, extension)
                if symbol:
                    symbols.append(symbol)

            if node.type in IMPORT_NODE_TYPES.get(language, set()):
                import_data = self._extract_import(node, contents, extension)
                if import_data:
                    imports.append(import_data)

        return {
            'file_path': file_path,
            'symbols': symbols,
            'imports': imports
        }

    def _traverse(self, node):
        yield node
        for child in node.children:
            yield from self._traverse(child)

    def _extract_symbol(self, node, contents, extension):
        try:
            start_line, _ = node.start_point
            end_line, _ = node.end_point
            name = None
            signature = None

            if extension == '.py':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = contents[name_node.start_byte:name_node.end_byte].strip()
                    signature = self._extract_definition_line(contents, node.start_byte)
                symbol_type = 'class' if node.type == 'class_definition' else 'function'

            elif extension == '.go':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = contents[name_node.start_byte:name_node.end_byte].strip()
                if node.type == 'type_spec':
                    symbol_type = 'type'
                    signature = self._extract_definition_line(contents, node.start_byte)
                else:
                    symbol_type = 'function'
                    signature = self._extract_definition_line(contents, node.start_byte)

            elif extension == '.php':
                name_node = node.child_by_field_name('name')
                if name_node:
                    name = contents[name_node.start_byte:name_node.end_byte].strip()
                if node.type == 'class_declaration':
                    symbol_type = 'class'
                elif node.type == 'interface_declaration':
                    symbol_type = 'interface'
                elif node.type == 'trait_declaration':
                    symbol_type = 'trait'
                else:
                    symbol_type = 'function'
                signature = self._extract_definition_line(contents, node.start_byte)

            else:
                return None

            if not name:
                return None

            return {
                'symbol_name': name,
                'symbol_type': symbol_type,
                'signature': signature,
                'start_line': start_line + 1,
                'end_line': end_line + 1
            }
        except Exception as exc:
            print(f'[LanguageRouter] Symbol extraction failed: {exc}', file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return None

    def _extract_definition_line(self, contents, start_byte):
        if start_byte is None or start_byte >= len(contents):
            return None
        line_start = contents.rfind('\n', 0, start_byte) + 1
        line_end = contents.find('\n', start_byte)
        if line_end == -1:
            line_end = len(contents)
        return contents[line_start:line_end].strip()

    def _extract_import(self, node, contents, extension):
        try:
            return {'import_text': self._node_text(node, contents)}
        except Exception as exc:
            print(f'[LanguageRouter] Import extraction failed: {exc}', file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            return None

    def _node_text(self, node, contents):
        return contents[node.start_byte:node.end_byte].strip()
