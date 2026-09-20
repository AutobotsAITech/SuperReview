#!/usr/bin/env python3
"""Bounded, read-only MCP tools over the three immutable commits in a review plan."""
import argparse
import json
from pathlib import Path
import sys

import superreview as sr

PROTOCOLS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")
PAGE_BYTES = 64 * 1024


def object_schema(properties, required):
    return {"type": "object", "properties": properties, "required": required,
            "additionalProperties": False}


def tools():
    side = {"type": "string", "enum": ["base", "head", "merge_base"]}
    path = {"type": "string", "description": "Literal repository-relative POSIX path."}
    page = {"type": "integer", "minimum": 0, "description": "Zero-based page, 100 entries each."}
    specs = [
        ("read_file", "Read committed text with line numbers. Does not follow symlinks or submodules.",
         {"side": side, "path": path, "start_line": {"type": "integer", "minimum": 1},
          "start_column": {"type": "integer", "minimum": 0, "description": "Zero-based character cursor for a long line. Follow next_line and next_column until null."},
          "line_count": {"type": "integer", "minimum": 1, "maximum": 200}}, ["side", "path"]),
        ("list_files", "List committed paths, including repository policy files. Results are paginated.",
         {"side": side, "contains": {"type": "string"}, "page": page}, ["side"]),
        ("search", "Find literal text in committed text files; paginated, fixed-string search.",
         {"side": side, "query": {"type": "string"}, "page": page}, ["side", "query"]),
        ("diff", "Read the merge-base-to-head patch for one changed manifest path, in pages.",
         {"path": path, "page": page}, ["path"]),
    ]
    return [{"name": name, "description": description, "inputSchema": object_schema(properties, required),
             "annotations": {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}}
            for name, description, properties, required in specs]


class Reader:
    def __init__(self, repo, plan, max_calls=200, events=None):
        self.repo, self.plan = sr.repository_root(repo), sr.validate_plan(plan)
        self.max_calls, self.calls = max_calls, 0
        self.definitions = {tool["name"]: tool for tool in tools()}
        self.events = Path(events) if events else None
        if self.events:
            self.calls = len(self.events.read_text().splitlines())

    def page(self, lines, number):
        sr.require(type(number) is int and number >= 0, "page must be a nonnegative integer")
        start = number * 100
        return {"lines": lines[start:start + 100], "next_page": number + 1 if start + 100 < len(lines) else None,
                "total_lines": len(lines)}

    def call(self, name, args):
        self.calls += 1
        event = {"tool": name if isinstance(name, str) and name in self.definitions else "unknown",
                 "ok": False, "budget_exhausted": self.calls > self.max_calls}
        try:
            result = self._call(name, args)
            event["ok"] = True
            return result
        finally:
            if self.events:
                with self.events.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(event) + "\n")

    def _call(self, name, args):
        sr.require(self.calls <= self.max_calls, "reader call budget exhausted; record incomplete coverage")
        sr.require(isinstance(name, str) and name in self.definitions, "unknown tool")
        spec = self.definitions[name]["inputSchema"]
        sr.require(isinstance(args, dict) and set(args) <= set(spec["properties"])
                   and set(spec["required"]) <= set(args), "invalid tool arguments")
        if "side" in args:
            sr.require(isinstance(args["side"], str) and args["side"] in ("base", "head", "merge_base"), "invalid side")
            ref = self.plan[args["side"]]
        if "path" in args:
            path = sr.repo_path(args["path"])
        if name == "read_file":
            entry = sr.git(self.repo, "ls-tree", "-z", ref, "--", path).split(b"\0")
            sr.require(len(entry) == 2 and entry[1] == b"", "path does not identify one committed file")
            metadata, actual = entry[0].split(b"\t", 1)
            mode, kind, oid = metadata.decode().split()
            sr.require(actual.decode() == path and mode in ("100644", "100755") and kind == "blob",
                       "only regular committed files may be read")
            data = sr.git(self.repo, "cat-file", "blob", oid)
            sr.require(b"\0" not in data, "binary content is not available as text")
            lines = data.decode("utf-8").splitlines()
            start, count = args.get("start_line", 1), args.get("line_count", 200)
            sr.require(type(start) is int and start >= 1 and type(count) is int and 1 <= count <= 200,
                       "invalid line window")
            column = args.get("start_column", 0)
            sr.require(type(column) is int and column >= 0, "invalid character cursor")
            sr.require(column == 0 or (start <= len(lines) and column < len(lines[start - 1])), "cursor is outside the line")
            # Leave room for metadata and JSON-escaped non-BMP characters.
            budget, rows, index = 3000, [], start - 1
            while index < len(lines) and len(rows) < count and budget > 0:
                text = lines[index][column:column + budget]
                end = column + len(text)
                rows.append({"line": index + 1, "text": text, "start_column": column,
                             "continued": end < len(lines[index])})
                budget -= len(text)
                if end < len(lines[index]):
                    column = end
                    break
                index, column = index + 1, 0
            result = {"lines": rows, "total_lines": len(lines),
                      "next_line": index + 1 if index < len(lines) else None,
                      "next_column": column if index < len(lines) else None}
        elif name == "list_files":
            contains = args.get("contains", "")
            sr.require(isinstance(contains, str) and len(contains) <= 300, "invalid path filter")
            paths = sr.git(self.repo, "ls-tree", "-r", "--name-only", "-z", ref).decode().split("\0")
            result = self.page([p for p in paths if p and contains in p], args.get("page", 0))
        elif name == "search":
            sr.string(args["query"], "query")
            sr.require(len(args["query"]) <= 300 and "\n" not in args["query"], "query must be a short literal")
            output = sr.git(self.repo, "grep", "--no-textconv", "--no-color", "-n", "-I", "-F",
                            "-e", args["query"], ref, "--", ok=(0, 1))
            result = self.page(output.decode().splitlines(), args.get("page", 0))
        else:
            file = next((f for f in self.plan["files"] if f["path"] == path), None)
            sr.require(file is not None, "diff path is outside the plan")
            output = sr.git(self.repo, "diff", "--no-ext-diff", "--no-textconv", "--no-color", "--no-relative",
                            "--find-renames", "--unified=3", "--inter-hunk-context=0",
                            self.plan["merge_base"], self.plan["head"], "--", file["old_path"], path)
            result = self.page(output.decode().splitlines(), args.get("page", 0))
        text = json.dumps(result, ensure_ascii=True)
        sr.require(len(text.encode()) <= PAGE_BYTES, "tool page exceeds 64 KiB; narrow the request or record a limitation")
        return {"content": [{"type": "text", "text": text}], "isError": False}


def serve(reader, source, output):
    initialized = False
    while True:
        raw = source.readline(PAGE_BYTES + 1)
        if not raw:
            return
        if len(raw) > PAGE_BYTES:
            return  # Fail the transport without buffering an unbounded request.
        ident = None
        try:
            request = json.loads(raw)
            sr.require(isinstance(request, dict) and request.get("jsonrpc") == "2.0", "invalid request")
            if "id" not in request:
                continue
            ident = request["id"]
            sr.require(type(ident) in (str, int), "invalid request identifier")
            method, params = request.get("method"), request.get("params", {})
            sr.require(isinstance(params, dict), "invalid parameters")
            if method == "initialize":
                version = params.get("protocolVersion")
                result = {"protocolVersion": version if version in PROTOCOLS else PROTOCOLS[0],
                          "capabilities": {"tools": {"listChanged": False}},
                          "serverInfo": {"name": "superreview-reader", "version": sr.VERSION}}
                initialized = True
            elif method == "ping":
                result = {}
            elif not initialized:
                raise sr.ReviewError("initialize first")
            elif method == "tools/list":
                result = {"tools": tools()}
            elif method == "tools/call":
                try:
                    result = reader.call(params.get("name"), params.get("arguments", {}))
                except (sr.ReviewError, OSError, UnicodeError, ValueError) as exc:
                    message = str(exc) if isinstance(exc, sr.ReviewError) else "repository read failed; record the limitation"
                    result = {"content": [{"type": "text", "text": message}], "isError": True}
            else:
                output.write(json.dumps({"jsonrpc": "2.0", "id": ident,
                                         "error": {"code": -32601, "message": "method not found"}}) + "\n")
                output.flush()
                continue
            response = {"jsonrpc": "2.0", "id": ident, "result": result}
        except (ValueError, TypeError, RecursionError):
            response = {"jsonrpc": "2.0", "id": ident,
                        "error": {"code": -32600, "message": "invalid request"}}
        output.write(json.dumps(response, ensure_ascii=True) + "\n")
        output.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--plan", required=True)
    parser.add_argument("--max-calls", type=int, default=200)
    parser.add_argument("--events")
    args = parser.parse_args()
    sr.require(1 <= args.max_calls <= 10000, "invalid reader call budget")
    serve(Reader(args.repo, sr.load_json(args.plan), args.max_calls, args.events), sys.stdin.buffer, sys.stdout)


if __name__ == "__main__":
    try:
        main()
    except (sr.ReviewError, OSError, UnicodeError):
        print("superreview-reader: initialization failed", file=sys.stderr)
        sys.exit(2)
