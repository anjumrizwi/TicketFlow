// Blazor Server has no native "download button" (unlike a plain <a download>
// pointing at a static file) since exports are generated per-request from
// live, user-scoped data held in the circuit — not a file on disk. This
// triggers a browser download from bytes already produced server-side by
// ReportService, without ever exposing a separate unauthenticated HTTP
// endpoint for the export (which would need its own auth path, since plain
// endpoints don't share the circuit-scoped CurrentUserAccessor).
window.downloadFileFromBytes = (fileName, contentType, base64Content) => {
    const link = document.createElement("a");
    link.href = `data:${contentType};base64,${base64Content}`;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
};
