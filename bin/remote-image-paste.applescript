-- Run by a Ghostty-only macOS Service. Keep the original terminal selected
-- even if the user switches tabs while an upload is running.
on run
    tell application "Ghostty"
        if (count of windows) is 0 then error "No Ghostty terminal is open."
        set targetID to id of focused terminal of selected tab of front window
        set targetTerminal to terminal id targetID
        set targetTitle to name of targetTerminal
    end tell

    set helperPath to (POSIX path of (path to home folder)) & "Library/Application Support/remote-image-paste/remote-image-paste"
    set helper to "/usr/bin/env PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin python3 " & quoted form of helperPath
    try
        do shell script (helper & " --matches-title " & quoted form of targetTitle)
    on error messageText number statusCode
        if statusCode is 3 then
            tell application "Ghostty" to send key "v" modifiers "control" to targetTerminal
            return
        end if
        display notification messageText with title "Remote image paste failed"
        error messageText number statusCode
    end try

    try
        set remotePath to do shell script helper
    on error messageText number statusCode
        if statusCode is 2 then
            try
                set clipboardText to the clipboard as text
            on error
                return
            end try
            -- Explicit text input avoids the duplicate paste observed with
            -- paste_from_clipboard in the original Ghostty/OpenCode integration.
            tell application "Ghostty" to input text clipboardText to targetTerminal
            return
        end if
        display notification messageText with title "Remote image paste failed"
        error messageText number statusCode
    end try

    tell application "Ghostty" to input text remotePath to targetTerminal
end run
