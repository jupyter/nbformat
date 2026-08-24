use once_cell::sync::OnceCell;
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyBytes, PyDict, PyFloat, PyInt, PyList, PyString};
use serde_json::{Map, Value};
use std::fmt::Write as _;

// ---------------------------------------------------------------------
// Schema (embedded at build time from the real nbformat package so the
// prototype validates against the exact same v4.5 schema Python uses).
// ---------------------------------------------------------------------
const SCHEMA_V45_STR: &str =
    include_str!("/home/user/nbformat/nbformat/v4/nbformat.v4.5.schema.json");

static COMPILED_SCHEMA: OnceCell<jsonschema::JSONSchema> = OnceCell::new();

fn get_schema() -> &'static jsonschema::JSONSchema {
    COMPILED_SCHEMA.get_or_init(|| {
        let schema_val: Value = serde_json::from_str(SCHEMA_V45_STR).expect("schema parses");
        jsonschema::JSONSchema::options()
            .with_draft(jsonschema::Draft::Draft4)
            .compile(&schema_val)
            .expect("schema compiles")
    })
}

// =======================================================================
// Python str .splitlines(keepends=True) - faithful re-implementation.
// CPython recognizes: \n \r \r\n \v \f \x1c \x1d \x1e \x85
// =======================================================================
fn is_line_boundary(c: char) -> bool {
    matches!(
        c,
        '\n' | '\r' | '\u{0b}' | '\u{0c}' | '\u{1c}' | '\u{1d}' | '\u{1e}' | '\u{85}' | '\u{2028}' | '\u{2029}'
    )
}

fn py_splitlines_keepends(s: &str) -> Vec<String> {
    let mut out = Vec::new();
    let chars: Vec<(usize, char)> = s.char_indices().collect();
    let mut start = 0usize;
    let mut i = 0usize;
    while i < chars.len() {
        let (byte_idx, c) = chars[i];
        if is_line_boundary(c) {
            let mut end_byte = byte_idx + c.len_utf8();
            // \r\n counts as a single boundary
            if c == '\r' && i + 1 < chars.len() && chars[i + 1].1 == '\n' {
                end_byte += 1;
                i += 1;
            }
            out.push(s[start..end_byte].to_string());
            start = end_byte;
        }
        i += 1;
    }
    if start < s.len() {
        out.push(s[start..].to_string());
    }
    out
}

// =======================================================================
// V1: reads() -- parse JSON in Rust, apply rejoin_lines + strip_transient
// on the serde_json::Value tree, then materialize NotebookNode objects.
// =======================================================================

fn is_json_mime(mime: &str) -> bool {
    mime == "application/json" || (mime.starts_with("application/") && mime.ends_with("+json"))
}

fn rejoin_mimebundle(data: &mut Map<String, Value>) {
    let keys: Vec<String> = data.keys().cloned().collect();
    for key in keys {
        let should_join = {
            if is_json_mime(&key) {
                false
            } else if let Some(Value::Array(arr)) = data.get(&key) {
                arr.iter().all(|v| v.is_string())
            } else {
                false
            }
        };
        if should_join {
            if let Some(Value::Array(arr)) = data.get(&key) {
                let joined: String = arr
                    .iter()
                    .map(|v| v.as_str().unwrap_or(""))
                    .collect();
                data.insert(key, Value::String(joined));
            }
        }
    }
}

/// Apply rejoin_lines + strip_transient to a notebook JSON tree, in place.
fn transform_read(nb: &mut Value) {
    if let Value::Object(top) = nb {
        // strip_transient on nb.metadata
        if let Some(Value::Object(meta)) = top.get_mut("metadata") {
            meta.remove("orig_nbformat");
            meta.remove("orig_nbformat_minor");
            meta.remove("signature");
        }
        if let Some(Value::Array(cells)) = top.get_mut("cells") {
            for cell in cells.iter_mut() {
                let Value::Object(cell_obj) = cell else { continue };

                // source: list[str] -> str
                if let Some(Value::Array(arr)) = cell_obj.get("source") {
                    if arr.iter().all(|v| v.is_string()) {
                        let joined: String =
                            arr.iter().map(|v| v.as_str().unwrap_or("")).collect();
                        cell_obj.insert("source".to_string(), Value::String(joined));
                    }
                }

                // attachments: mimebundle rejoin
                if let Some(Value::Object(attachments)) = cell_obj.get_mut("attachments") {
                    for (_name, bundle) in attachments.iter_mut() {
                        if let Value::Object(bundle_obj) = bundle {
                            rejoin_mimebundle(bundle_obj);
                        }
                    }
                }

                // strip_transient on cell.metadata.trusted
                if let Some(Value::Object(cmeta)) = cell_obj.get_mut("metadata") {
                    cmeta.remove("trusted");
                }

                let is_code = cell_obj.get("cell_type").and_then(|v| v.as_str()) == Some("code");
                if is_code {
                    if let Some(Value::Array(outputs)) = cell_obj.get_mut("outputs") {
                        for output in outputs.iter_mut() {
                            let Value::Object(out_obj) = output else { continue };
                            let output_type =
                                out_obj.get("output_type").and_then(|v| v.as_str()).unwrap_or("").to_string();
                            if output_type == "execute_result" || output_type == "display_data" {
                                if let Some(Value::Object(data)) = out_obj.get_mut("data") {
                                    rejoin_mimebundle(data);
                                }
                            } else if !output_type.is_empty() {
                                if let Some(Value::Array(arr)) = out_obj.get("text") {
                                    if arr.iter().all(|v| v.is_string()) {
                                        let joined: String =
                                            arr.iter().map(|v| v.as_str().unwrap_or("")).collect();
                                        out_obj.insert("text".to_string(), Value::String(joined));
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

/// Build a Python object tree from a serde_json::Value, wrapping every
/// JSON object as a real `nbformat.notebooknode.NotebookNode` instance
/// (matching `from_dict`'s semantics), via the class constructor which
/// takes the fast dict.__init__ path since children are pre-converted.
fn value_to_py(py: Python<'_>, v: &Value, node_cls: &Bound<'_, PyAny>) -> PyResult<PyObject> {
    match v {
        Value::Null => Ok(py.None()),
        Value::Bool(b) => Ok(b.into_py(py)),
        Value::Number(n) => {
            if let Some(i) = n.as_i64() {
                Ok(i.into_py(py))
            } else if let Some(u) = n.as_u64() {
                Ok(u.into_py(py))
            } else {
                Ok(n.as_f64().unwrap_or(0.0).into_py(py))
            }
        }
        Value::String(s) => Ok(s.into_py(py)),
        Value::Array(arr) => {
            let list = PyList::empty_bound(py);
            for item in arr {
                list.append(value_to_py(py, item, node_cls)?)?;
            }
            Ok(list.into())
        }
        Value::Object(map) => {
            let dict = PyDict::new_bound(py);
            for (k, val) in map {
                dict.set_item(k, value_to_py(py, val, node_cls)?)?;
            }
            let node = node_cls.call1((dict,))?;
            Ok(node.into())
        }
    }
}

#[pyfunction]
fn reads(py: Python<'_>, s: &str) -> PyResult<PyObject> {
    let mut val: Value =
        serde_json::from_str(s).map_err(|e| PyValueError::new_err(format!("JSON parse error: {e}")))?;
    transform_read(&mut val);
    let module = py.import_bound("nbformat.notebooknode")?;
    let node_cls = module.getattr("NotebookNode")?;
    value_to_py(py, &val, &node_cls)
}

// =======================================================================
// V3: validate() straight from source bytes/text, never building Python
// objects. Also a fused read_validate() -> NotebookNode pipeline.
// =======================================================================

#[pyfunction]
fn validate_json(s: &str) -> PyResult<()> {
    let val: Value =
        serde_json::from_str(s).map_err(|e| PyValueError::new_err(format!("JSON parse error: {e}")))?;
    let schema = get_schema();
    if let Err(mut errors) = schema.validate(&val) {
        if let Some(first) = errors.next() {
            return Err(PyValueError::new_err(format!("{first}")));
        }
    }
    Ok(())
}

#[pyfunction]
fn is_valid_json(s: &str) -> PyResult<bool> {
    let val: Value =
        serde_json::from_str(s).map_err(|e| PyValueError::new_err(format!("JSON parse error: {e}")))?;
    let schema = get_schema();
    Ok(schema.is_valid(&val))
}

#[pyfunction]
fn read_validate(py: Python<'_>, s: &str) -> PyResult<PyObject> {
    let val: Value =
        serde_json::from_str(s).map_err(|e| PyValueError::new_err(format!("JSON parse error: {e}")))?;
    let schema = get_schema();
    if let Err(mut errors) = schema.validate(&val) {
        if let Some(first) = errors.next() {
            return Err(PyValueError::new_err(format!("{first}")));
        }
    }
    let mut val = val;
    transform_read(&mut val);
    let module = py.import_bound("nbformat.notebooknode")?;
    let node_cls = module.getattr("NotebookNode")?;
    value_to_py(py, &val, &node_cls)
}

// =======================================================================
// V2: writes() directly from the live Python object graph -- no deepcopy,
// no intermediate tree rebuild. Walks PyDict/PyList in place (read-only)
// and streams JSON text matching nbformat's BytesEncoder / json.dumps
// (indent=1, sort_keys=True, separators=(",", ": "), ensure_ascii=False).
// =======================================================================

const NON_TEXT_SPLIT_MIMES: [&str; 2] = ["application/javascript", "image/svg+xml"];

fn mime_should_split(key: &str) -> bool {
    key.starts_with("text/") || NON_TEXT_SPLIT_MIMES.contains(&key)
}

fn json_escape_into(out: &mut String, s: &str) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{08}' => out.push_str("\\b"),
            '\u{0c}' => out.push_str("\\f"),
            c if (c as u32) < 0x20 => {
                let _ = write!(out, "\\u{:04x}", c as u32);
            }
            c => out.push(c),
        }
    }
    out.push('"');
}

fn write_indent(out: &mut String, depth: usize) {
    out.push('\n');
    for _ in 0..depth {
        out.push(' ');
    }
}

/// Context describing where we are in the notebook tree, so we know which
/// key-stripping / line-splitting rules from rwbase.py apply at this node.
#[derive(Clone, Copy)]
enum Ctx {
    Root,
    NbMetadata,
    CellMetadata,
    CellSource,
    Mimebundle,
    StreamText,
    Cells,
    Cell,
    Outputs,
    Output,
    Attachments,
    AttachmentBundle,
    Plain,
}

fn py_dict_sorted_keys<'py>(dict: &Bound<'py, PyDict>) -> PyResult<Vec<Bound<'py, PyString>>> {
    let mut keys: Vec<Bound<PyString>> = Vec::with_capacity(dict.len());
    for k in dict.keys() {
        keys.push(k.downcast_into::<PyString>().map_err(|_| {
            PyTypeError::new_err("nbf_rust writes: only string keys are supported")
        })?);
    }
    keys.sort_by(|a, b| a.to_string_lossy().cmp(&b.to_string_lossy()));
    Ok(keys)
}

fn serialize_value(py: Python<'_>, out: &mut String, obj: &Bound<'_, PyAny>, depth: usize, ctx: Ctx) -> PyResult<()> {
    if obj.is_none() {
        out.push_str("null");
        return Ok(());
    }
    if let Ok(b) = obj.downcast::<PyBool>() {
        out.push_str(if b.is_true() { "true" } else { "false" });
        return Ok(());
    }
    if let Ok(s) = obj.downcast::<PyString>() {
        let txt = s.to_str()?;
        // Cell "source" and split-eligible mimebundle text/stream text get
        // split into a list-of-lines on write (rwbase.split_lines).
        let splits: Option<Vec<String>> = match ctx {
            Ctx::CellSource | Ctx::StreamText => Some(py_splitlines_keepends(txt)),
            _ => None,
        };
        if let Some(lines) = splits {
            serialize_str_list(out, &lines, depth);
        } else {
            json_escape_into(out, txt);
        }
        return Ok(());
    }
    if let Ok(b) = obj.downcast::<PyBytes>() {
        // BytesEncoder: decode as ascii
        let bytes = b.as_bytes();
        let s = std::str::from_utf8(bytes)
            .map_err(|_| PyValueError::new_err("bytes value is not valid ascii"))?;
        json_escape_into(out, s);
        return Ok(());
    }
    if obj.downcast::<PyInt>().is_ok() {
        let repr = obj.repr()?;
        out.push_str(repr.to_str()?);
        return Ok(());
    }
    if let Ok(_f) = obj.downcast::<PyFloat>() {
        // Delegate to Python's own repr for perfect float-formatting
        // fidelity (this is what CPython's json encoder itself uses),
        // with json's NaN/Infinity special-casing.
        let val: f64 = obj.extract()?;
        if val.is_nan() {
            out.push_str("NaN");
        } else if val.is_infinite() {
            out.push_str(if val > 0.0 { "Infinity" } else { "-Infinity" });
        } else {
            let repr = obj.repr()?;
            out.push_str(repr.to_str()?);
        }
        return Ok(());
    }
    if let Ok(list) = obj.downcast::<PyList>() {
        let n = list.len();
        if n == 0 {
            out.push_str("[]");
            return Ok(());
        }
        out.push('[');
        let child_ctx = match ctx {
            Ctx::Cells => Ctx::Cell,
            Ctx::Outputs => Ctx::Output,
            _ => Ctx::Plain,
        };
        for (i, item) in list.iter().enumerate() {
            if i > 0 {
                out.push(',');
            }
            write_indent(out, depth + 1);
            serialize_value(py, out, &item, depth + 1, child_ctx)?;
        }
        write_indent(out, depth);
        out.push(']');
        return Ok(());
    }
    if let Ok(dict) = obj.downcast::<PyDict>() {
        serialize_dict(py, out, dict, depth, ctx)?;
        return Ok(());
    }
    Err(PyTypeError::new_err(format!(
        "nbf_rust writes: unsupported type {}",
        obj.get_type().name()?
    )))
}

fn serialize_str_list(out: &mut String, lines: &[String], depth: usize) {
    if lines.is_empty() {
        out.push_str("[]");
        return;
    }
    out.push('[');
    for (i, line) in lines.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        write_indent(out, depth + 1);
        json_escape_into(out, line);
    }
    write_indent(out, depth);
    out.push(']');
}

fn serialize_dict(
    py: Python<'_>,
    out: &mut String,
    dict: &Bound<'_, PyDict>,
    depth: usize,
    ctx: Ctx,
) -> PyResult<()> {
    let mut keys = py_dict_sorted_keys(dict)?;

    // strip_transient: drop keys that never make it to the file.
    match ctx {
        Ctx::NbMetadata => {
            keys.retain(|k| {
                let s = k.to_string_lossy();
                s != "orig_nbformat" && s != "orig_nbformat_minor" && s != "signature"
            });
        }
        Ctx::CellMetadata => {
            keys.retain(|k| k.to_string_lossy() != "trusted");
        }
        _ => {}
    }

    if keys.is_empty() {
        out.push_str("{}");
        return Ok(());
    }

    out.push('{');
    let mut cell_type: Option<String> = None;
    let mut output_type: Option<String> = None;
    if matches!(ctx, Ctx::Cell) {
        if let Ok(Some(v)) = dict.get_item("cell_type") {
            cell_type = v.extract::<String>().ok();
        }
    }
    if matches!(ctx, Ctx::Output) {
        if let Ok(Some(v)) = dict.get_item("output_type") {
            output_type = v.extract::<String>().ok();
        }
    }

    for (i, key) in keys.iter().enumerate() {
        if i > 0 {
            out.push(',');
        }
        write_indent(out, depth + 1);
        let key_str = key.to_str()?;
        json_escape_into(out, key_str);
        out.push_str(": ");

        let value = dict.get_item(key)?.expect("key from dict.keys()");

        let child_ctx = match (ctx, key_str) {
            (Ctx::Root, "metadata") => Ctx::NbMetadata,
            (Ctx::Root, "cells") => Ctx::Cells,
            (Ctx::Cell, "metadata") => Ctx::CellMetadata,
            (Ctx::Cell, "source") => Ctx::CellSource,
            (Ctx::Cell, "attachments") => Ctx::Attachments,
            (Ctx::Cell, "outputs") if cell_type.as_deref() == Some("code") => Ctx::Outputs,
            (Ctx::Attachments, _) => Ctx::AttachmentBundle,
            (Ctx::Output, "data")
                if matches!(
                    output_type.as_deref(),
                    Some("execute_result") | Some("display_data")
                ) =>
            {
                Ctx::Mimebundle
            }
            (Ctx::Output, "text") if output_type.as_deref() == Some("stream") => Ctx::StreamText,
            (Ctx::AttachmentBundle, mime) | (Ctx::Mimebundle, mime) => {
                if mime_should_split(mime) {
                    Ctx::StreamText // reuse: str -> split-lines-on-write
                } else {
                    Ctx::Plain
                }
            }
            _ => Ctx::Plain,
        };

        serialize_value(py, out, &value, depth + 1, child_ctx)?;
    }
    write_indent(out, depth);
    out.push('}');
    Ok(())
}

#[pyfunction]
fn writes(py: Python<'_>, nb: &Bound<'_, PyAny>) -> PyResult<String> {
    let dict = nb
        .downcast::<PyDict>()
        .map_err(|_| PyTypeError::new_err("nbf_rust writes: expected a dict-like notebook"))?;
    let mut out = String::with_capacity(1 << 16);
    serialize_dict(py, &mut out, dict, 0, Ctx::Root)?;
    Ok(out)
}

// =======================================================================
#[pymodule]
fn nbf_rust(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(reads, m)?)?;
    m.add_function(wrap_pyfunction!(writes, m)?)?;
    m.add_function(wrap_pyfunction!(validate_json, m)?)?;
    m.add_function(wrap_pyfunction!(is_valid_json, m)?)?;
    m.add_function(wrap_pyfunction!(read_validate, m)?)?;
    Ok(())
}
