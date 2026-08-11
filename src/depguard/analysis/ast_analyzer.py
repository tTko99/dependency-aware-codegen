from __future__ import annotations

import ast

from depguard.schemas import AliasBinding, AnalysisResult, APIReference, ImportReference

RETURN_TYPE_HINTS = {
    "pandas.DataFrame": "pandas.DataFrame",
    "pandas.Series": "pandas.Series",
    "pandas.read_csv": "pandas.DataFrame",
    "pandas.read_excel": "pandas.DataFrame",
    "numpy.array": "numpy.ndarray",
    "pathlib.Path": "pathlib.Path",
    "requests.get": "requests.Response",
}


class DependencyAnalyzer(ast.NodeVisitor):
    """Extract imports, aliases, and external API references from Python source."""

    def analyze(self, code: str) -> AnalysisResult:
        self._code = code
        self.imports: list[ImportReference] = []
        self.alias_table: dict[str, AliasBinding] = {}
        self.api_references: list[APIReference] = []
        self._seen_api_keys: set[tuple[str, int, str]] = set()
        self._variable_types: dict[str, str] = {}

        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return AnalysisResult(
                imports=[],
                alias_table={},
                api_references=[],
                syntax_error=f"{exc.msg} at line {exc.lineno}",
            )

        self.visit(tree)
        return AnalysisResult(
            imports=self.imports,
            alias_table=dict(sorted(self.alias_table.items())),
            api_references=self.api_references,
            syntax_error=None,
        )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            ref = ImportReference(
                module=alias.name,
                name=None,
                alias=alias.asname,
                line_number=node.lineno,
                is_from_import=False,
            )
            self.imports.append(ref)

            if alias.asname:
                local_name = alias.asname
                canonical_path = alias.name
            else:
                local_name = alias.name.split(".", maxsplit=1)[0]
                canonical_path = local_name
            self.alias_table[local_name] = AliasBinding(
                local_name=local_name,
                canonical_path=canonical_path,
                import_type="import",
                line_number=node.lineno,
            )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            if alias.name == "*":
                self.imports.append(
                    ImportReference(
                        module=module,
                        name=alias.name,
                        alias=alias.asname,
                        line_number=node.lineno,
                        is_from_import=True,
                        level=node.level,
                    )
                )
                continue

            ref = ImportReference(
                module=module,
                name=alias.name,
                alias=alias.asname,
                line_number=node.lineno,
                is_from_import=True,
                level=node.level,
            )
            self.imports.append(ref)

            canonical_path = ref.canonical_path
            local_name = alias.asname or alias.name
            self.alias_table[local_name] = AliasBinding(
                local_name=local_name,
                canonical_path=canonical_path,
                import_type="from",
                line_number=node.lineno,
            )
            if node.level == 0 and module:
                api_ref = self._make_reference(
                    canonical_path.split("."),
                    node=node,
                    call_type="import_object",
                    source=alias.name,
                    receiver=local_name,
                    is_call=False,
                    arg_count=None,
                    keyword_names=(),
                )
                if api_ref:
                    self._add_api_reference(api_ref)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        inferred_type = self._infer_call_return_type(node.value)
        if inferred_type:
            for target in node.targets:
                for name in self._target_names(target):
                    self._variable_types[name] = inferred_type
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        inferred_type = self._infer_call_return_type(node.value) if node.value else None
        if inferred_type:
            for name in self._target_names(node.target):
                self._variable_types[name] = inferred_type
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        ref = self._reference_from_call(node)
        if ref:
            self._add_api_reference(ref)
        self.generic_visit(node)

    def _reference_from_call(self, node: ast.Call) -> APIReference | None:
        chain = self._attribute_chain(node.func)
        if not chain:
            return None

        keyword_names = tuple(keyword.arg for keyword in node.keywords if keyword.arg)
        source = ast.get_source_segment(self._code, node.func) or ".".join(chain)
        return self._canonicalize_chain(
            chain,
            node=node,
            call_type="call",
            source=source,
            is_call=True,
            arg_count=len(node.args),
            keyword_names=keyword_names,
        )

    def _canonicalize_chain(
        self,
        chain: list[str],
        *,
        node: ast.AST,
        call_type: str,
        source: str,
        is_call: bool,
        arg_count: int | None,
        keyword_names: tuple[str, ...],
    ) -> APIReference | None:
        if not chain:
            return None

        base = chain[0]
        receiver = base
        if base in self.alias_table:
            binding = self.alias_table[base]
            canonical_parts = binding.canonical_path.split(".") + chain[1:]
            if binding.import_type == "from" and len(chain) == 1:
                resolved_call_type = "imported_callable" if is_call else "import_object"
            elif len(chain) > 1:
                resolved_call_type = "function_or_attribute"
            else:
                resolved_call_type = call_type
        elif base in self._variable_types:
            canonical_parts = self._variable_types[base].split(".") + chain[1:]
            resolved_call_type = "method_or_attribute"
        else:
            return None

        return self._make_reference(
            canonical_parts,
            node=node,
            call_type=resolved_call_type,
            source=source,
            receiver=receiver,
            is_call=is_call,
            arg_count=arg_count,
            keyword_names=keyword_names,
        )

    def _make_reference(
        self,
        canonical_parts: list[str],
        *,
        node: ast.AST,
        call_type: str,
        source: str,
        receiver: str | None,
        is_call: bool,
        arg_count: int | None,
        keyword_names: tuple[str, ...],
    ) -> APIReference | None:
        if len(canonical_parts) < 2:
            return None
        canonical_path = ".".join(canonical_parts)
        return APIReference(
            canonical_path=canonical_path,
            package=canonical_parts[0],
            module=".".join(canonical_parts[:-1]),
            object_path=canonical_parts[-1],
            call_type=call_type,
            line_number=getattr(node, "lineno", 0),
            source=source,
            receiver=receiver,
            arg_count=arg_count,
            keyword_names=keyword_names,
            is_call=is_call,
        )

    def _infer_call_return_type(self, node: ast.AST | None) -> str | None:
        if not isinstance(node, ast.Call):
            return None
        ref = self._reference_from_call(node)
        if not ref:
            return None
        if ref.canonical_path in RETURN_TYPE_HINTS:
            return RETURN_TYPE_HINTS[ref.canonical_path]
        if ref.canonical_path.endswith(".DataFrame"):
            return "pandas.DataFrame"
        if ref.canonical_path.endswith(".Series"):
            return "pandas.Series"
        return None

    def _add_api_reference(self, ref: APIReference) -> None:
        key = (ref.canonical_path, ref.line_number, ref.source)
        if key not in self._seen_api_keys:
            self._seen_api_keys.add(key)
            self.api_references.append(ref)

    @staticmethod
    def _attribute_chain(node: ast.AST) -> list[str] | None:
        if isinstance(node, ast.Name):
            return [node.id]
        if isinstance(node, ast.Attribute):
            parent = DependencyAnalyzer._attribute_chain(node.value)
            if parent:
                return parent + [node.attr]
        return None

    @staticmethod
    def _target_names(node: ast.AST) -> list[str]:
        if isinstance(node, ast.Name):
            return [node.id]
        if isinstance(node, (ast.Tuple, ast.List)):
            names: list[str] = []
            for element in node.elts:
                names.extend(DependencyAnalyzer._target_names(element))
            return names
        return []
