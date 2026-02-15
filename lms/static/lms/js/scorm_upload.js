/**
 * SCORM package direct-to-S3 upload.
 *
 * Three-phase flow:
 * 1. Request presigned POST URL from Django.
 * 2. Upload file directly to S3 (XHR for progress events).
 * 3. Finalize: tell Django to create the SCORMPackage from the S3 object.
 */
(function () {
    "use strict";

    const config = window.SCORM_UPLOAD_CONFIG;
    if (!config) return;

    const getCookie = (name) => {
        if (!document.cookie) return null;
        const match = document.cookie
            .split(";")
            .map((c) => c.trim())
            .find((c) => c.startsWith(name + "="));
        return match ? decodeURIComponent(match.split("=")[1]) : null;
    };

    const titleInput = document.getElementById("id_title");
    const descriptionInput = document.getElementById("id_description");
    const fileInput = document.getElementById("id_package_file");
    const submitBtn = document.getElementById("upload-submit");
    const progressContainer = document.getElementById("upload-progress");
    const progressBar = document.getElementById("progress-bar");
    const statusText = document.getElementById("upload-status");
    const errorDiv = document.getElementById("upload-error");

    const showError = (msg) => {
        errorDiv.textContent = msg;
        errorDiv.style.display = "block";
    };

    const clearError = () => {
        errorDiv.textContent = "";
        errorDiv.style.display = "none";
    };

    const setProgress = (pct, label) => {
        progressBar.style.width = pct + "%";
        progressBar.textContent = Math.round(pct) + "%";
        if (label) statusText.textContent = label;
    };

    const setSubmitEnabled = (enabled) => {
        submitBtn.disabled = !enabled;
        submitBtn.style.opacity = enabled ? "1" : "0.6";
        submitBtn.style.cursor = enabled ? "pointer" : "not-allowed";
    };

    // Auto-populate title from filename (minus .zip extension).
    // Track whether the current title was auto-filled so we can update it
    // when the user re-selects a different file, without overwriting a
    // manually entered title.
    let autoFilledTitle = "";
    fileInput.addEventListener("change", () => {
        const file = fileInput.files[0];
        if (!file) return;
        const current = titleInput.value.trim();
        if (!current || current === autoFilledTitle) {
            autoFilledTitle = file.name.replace(/\.zip$/i, "");
            titleInput.value = autoFilledTitle;
        }
    });

    submitBtn.addEventListener("click", async () => {
        clearError();

        const title = titleInput.value.trim();
        if (!title) {
            showError("Title is required.");
            titleInput.focus();
            return;
        }

        const file = fileInput.files[0];
        if (!file) {
            showError("Please select a SCORM package (.zip) file.");
            return;
        }

        if (!file.name.toLowerCase().endsWith(".zip")) {
            showError("Only .zip files are accepted.");
            return;
        }

        setSubmitEnabled(false);
        progressContainer.style.display = "block";
        setProgress(0, "Requesting upload URL...");

        const csrfToken = getCookie("csrftoken");

        // Phase 1: Get presigned POST URL
        let presigned;
        try {
            const resp = await fetch(config.presignedUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify({ filename: file.name }),
            });
            const contentType = resp.headers.get("Content-Type") || "";
            if (!contentType.includes("application/json")) {
                showError("Session expired or server error. Please reload the page.");
                setSubmitEnabled(true);
                progressContainer.style.display = "none";
                return;
            }
            const data = await resp.json();
            if (!resp.ok) {
                showError(data.error || "Failed to get upload URL.");
                setSubmitEnabled(true);
                progressContainer.style.display = "none";
                return;
            }
            presigned = data;
        } catch (err) {
            showError("Network error requesting upload URL.");
            setSubmitEnabled(true);
            progressContainer.style.display = "none";
            return;
        }

        // Phase 2: Upload directly to S3 via XHR (for progress events)
        setProgress(0, "Uploading to S3...");

        const uploadSuccess = await new Promise((resolve) => {
            const formData = new FormData();
            // Presigned fields must come before the file
            Object.entries(presigned.fields).forEach(([key, value]) => {
                formData.append(key, value);
            });
            formData.append("file", file);

            const xhr = new XMLHttpRequest();
            xhr.open("POST", presigned.url, true);

            xhr.upload.addEventListener("progress", (e) => {
                if (e.lengthComputable) {
                    const pct = (e.loaded / e.total) * 100;
                    setProgress(pct, "Uploading to S3...");
                }
            });

            xhr.addEventListener("load", () => {
                if (xhr.status >= 200 && xhr.status < 300) {
                    resolve(true);
                } else {
                    showError(
                        "Upload to S3 failed (HTTP " + xhr.status + "). Please try again."
                    );
                    resolve(false);
                }
            });

            xhr.addEventListener("error", () => {
                showError("Network error during upload. Please try again.");
                resolve(false);
            });

            xhr.send(formData);
        });

        if (!uploadSuccess) {
            setSubmitEnabled(true);
            return;
        }

        // Phase 3: Finalize — tell Django to create the package
        setProgress(100, "Processing SCORM package...");

        try {
            const resp = await fetch(config.finalizeUrl, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken,
                },
                body: JSON.stringify({
                    s3_key: presigned.s3_key,
                    title: title,
                    description: descriptionInput.value.trim(),
                }),
            });
            const finalizeContentType = resp.headers.get("Content-Type") || "";
            if (!finalizeContentType.includes("application/json")) {
                showError("Session expired or server error. Please reload the page.");
                setSubmitEnabled(true);
                return;
            }
            const data = await resp.json();
            if (!resp.ok) {
                showError(data.error || "Failed to process SCORM package.");
                setSubmitEnabled(true);
                return;
            }

            statusText.textContent = "Done! Redirecting...";
            window.location.assign(data.redirect_url);
        } catch (err) {
            showError("Network error during finalization. The file was uploaded but processing failed.");
            setSubmitEnabled(true);
        }
    });
})();
