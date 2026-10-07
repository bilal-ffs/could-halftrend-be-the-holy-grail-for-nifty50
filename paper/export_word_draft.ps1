param(
    [string]$DraftDirectory = "$PSScriptRoot\HalfTrend_NIFTY50_Review_Draft"
)

$draftRoot = (Resolve-Path -LiteralPath $DraftDirectory).Path
$htmlPath = Join-Path $draftRoot 'HalfTrend_NIFTY50_Review_Draft.html'
$docxPath = Join-Path $draftRoot 'HalfTrend_NIFTY50_Review_Draft.docx'
$pdfPath = Join-Path $draftRoot 'HalfTrend_NIFTY50_Review_Draft.pdf'
$word = $null
$document = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $word.AutomationSecurity = 3
    $document = $word.Documents.Open($htmlPath, $false, $false)
    $document.PageSetup.PageWidth = 595.3
    $document.PageSetup.PageHeight = 841.9
    $document.PageSetup.TopMargin = 54
    $document.PageSetup.BottomMargin = 54
    $document.PageSetup.LeftMargin = 54
    $document.PageSetup.RightMargin = 54
    $document.Styles.Item('Normal').Font.Name = 'Times New Roman'
    $document.Styles.Item('Normal').Font.Size = 11
    foreach ($table in $document.Tables) {
        $table.Rows.Item(1).HeadingFormat = -1
        $table.Rows.AllowBreakAcrossPages = 0
        $table.Range.Font.Size = 9
        $table.Range.ParagraphFormat.SpaceAfter = 2
        $table.Range.ParagraphFormat.SpaceBefore = 2
    }
    $header = $document.Sections.Item(1).Headers.Item(1).Range
    $header.Text = 'HALFTREND ON NIFTY 50 | AUTHOR-REVIEW WORKING PAPER'
    $header.Font.Name = 'Calibri'
    $header.Font.Size = 8
    $header.ParagraphFormat.Alignment = 2
    $footer = $document.Sections.Item(1).Footers.Item(1).Range
    $footer.Text = 'Mohd Bilal | Author-review draft | Page '
    $footer.Font.Name = 'Calibri'
    $footer.Font.Size = 8
    $footer.ParagraphFormat.Alignment = 1
    $footer.Collapse(0)
    $null = $footer.Fields.Add($footer, 33)
    $document.Repaginate()
    $document.SaveAs2($docxPath, 16)
    $document.ExportAsFixedFormat($pdfPath, 17)
    $pages = $document.ComputeStatistics(2)
    $proof = @{
        word_opened_and_exported = $true
        pages = $pages
        tables = $document.Tables.Count
        embedded_figures = $document.InlineShapes.Count
        word_version = $word.Version
        docx = $docxPath
        pdf = $pdfPath
    }
    $proof | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $draftRoot 'word_export_verification.json') -Encoding UTF8
    Write-Output "Word draft and PDF preview exported: $pages pages, $($proof.tables) tables, $($proof.embedded_figures) figures."
} finally {
    if ($null -ne $document) {
        $document.Close(0)
        $null = [Runtime.InteropServices.Marshal]::ReleaseComObject($document)
    }
    if ($null -ne $word) {
        $word.Quit()
        $null = [Runtime.InteropServices.Marshal]::ReleaseComObject($word)
    }
}
