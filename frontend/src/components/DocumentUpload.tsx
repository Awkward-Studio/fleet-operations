"use client";

import React, { useRef, useState, DragEvent } from "react";
import { Upload, FileText, Trash2, Eye, RefreshCw, AlertTriangle, Loader2 } from "lucide-react";
import { UploadedAsset, uploadAsset } from "@/lib/api";

interface DocumentUploadProps {
  value: UploadedAsset | null;
  onChange: (asset: UploadedAsset | null) => void;
  placeholder?: string;
  allowedExtensions?: string[]; // e.g., ['.pdf', '.jpg', '.jpeg', '.png']
}

export function DocumentUpload({
  value,
  onChange,
  placeholder = "Upload document (PDF or Image)",
  allowedExtensions = [".pdf", ".jpg", ".jpeg", ".png"],
}: DocumentUploadProps) {
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    if (!uploading && !value) {
      setDragOver(true);
    }
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
  };

  const handleDrop = async (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);

    if (uploading || value) return;

    const file = e.dataTransfer.files?.[0];
    if (file) {
      await processFile(file);
    }
  };

  const handleClick = () => {
    if (!uploading && !value && fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      await processFile(file);
    }
  };

  const processFile = async (file: File) => {
    setError(null);

    // Validate extension
    const extension = "." + file.name.split(".").pop()?.toLowerCase();
    if (!allowedExtensions.includes(extension)) {
      setError(`Unsupported file format. Allowed: ${allowedExtensions.join(", ")}`);
      return;
    }

    setUploading(true);
    setProgress(0);

    try {
      // Determine asset kind
      const kind = file.type.startsWith("image/") ? "image" : "pdf";
      const asset = await uploadAsset(file, kind, (p) => {
        setProgress(p);
      });
      onChange(asset);
    } catch (err: any) {
      setError(err.message || "Failed to upload file.");
    } finally {
      setUploading(false);
    }
  };

  const handleRemove = (e: React.MouseEvent) => {
    e.stopPropagation();
    onChange(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <div style={{ position: "relative", width: "100%" }}>
      {/* Hidden File Input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept={allowedExtensions.join(",")}
        style={{ display: "none" }}
      />

      {value ? (
        /* Upload Success State */
        <div className="doc-upload-success-container">
          <div className="doc-upload-file-info">
            <FileText size={18} />
            <span className="doc-upload-filename" title={value.original_name}>
              {value.original_name}
            </span>
          </div>
          <div className="doc-upload-actions">
            <a
              href={value.href}
              target="_blank"
              rel="noopener noreferrer"
              className="doc-upload-action-btn"
              title="View Document"
              onClick={(e) => e.stopPropagation()}
            >
              <Eye size={16} />
            </a>
            <button
              type="button"
              className="doc-upload-action-btn delete"
              onClick={handleRemove}
              title="Remove Document"
            >
              <Trash2 size={16} />
            </button>
          </div>
        </div>
      ) : uploading ? (
        /* Upload Progress State */
        <div className="doc-upload-box" style={{ cursor: "default" }}>
          <div className="doc-upload-progress-container">
            <div style={{ display: "flex", justifyContent: "space-between", width: "100%", fontSize: 12, color: "var(--muted)", fontWeight: 500 }}>
              <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <Loader2 size={14} className="animate-spin" /> Uploading...
              </span>
              <span>{progress}%</span>
            </div>
            <div className="doc-upload-progress-bar-bg">
              <div className="doc-upload-progress-bar-fill" style={{ width: `${progress}%` }}></div>
            </div>
          </div>
        </div>
      ) : (
        /* Placeholder / Drag & Drop Dropzone State */
        <div
          className={`doc-upload-box ${dragOver ? "drag-over" : ""}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={handleClick}
        >
          <div className="doc-upload-placeholder">
            <Upload size={22} style={{ color: "var(--accent)" }} />
            <span>{placeholder}</span>
            <small style={{ color: "var(--muted)" }}>
              Drag & drop or click to browse ({allowedExtensions.join(", ")})
            </small>
          </div>
        </div>
      )}

      {/* Error Message */}
      {error && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            color: "var(--danger)",
            fontSize: 11,
            marginTop: 4,
            fontWeight: 500,
          }}
        >
          <AlertTriangle size={12} />
          <span>{error}</span>
          <button
            type="button"
            onClick={() => setError(null)}
            style={{
              background: "transparent",
              border: "none",
              color: "var(--muted)",
              cursor: "pointer",
              padding: "0 4px",
              textDecoration: "underline",
              fontSize: 11,
            }}
          >
            Dismiss
          </button>
        </div>
      )}
    </div>
  );
}
