-- Run by the "Remote Image Paste" Ghostty-only macOS Service.
--
-- The terminal is captured before uploading so switching Ghostty tabs cannot
-- redirect the paste. The helper is called as an installed console script so
-- it runs in the same environment that installed it.
on run
    tell application "Ghostty"
        if (count of windows) is 0 then error "No Ghostty terminal is open."
        set targetID to id of focused terminal of selected tab of front window
        set targetTerminal to terminal id targetID
        set targetTitle to name of targetTerminal
    end tell

    try
        do shell script "remote-image-paste --matches-title " & quoted form of targetTitle
    on error messageText number statusCode
        -- Not our remote terminal: leave Control-V alone.
        if statusCode is 3 then
            tell application "Ghostty" to send key "v" modifiers "control" to targetTerminal
            return
        end if
        display notification messageText with title "Remote image paste failed"
        error messageText number statusCode
    end try

    try
        set remotePath to do shell script "remote-image-paste"
    on error messageText number statusCode
        -- No image on the clipboard: paste the text exactly once. Explicit text
        -- input avoids the duplication seen with paste_from_clipboard.
        if statusCode is 2 then
            try
                set clipboardText to the clipboard as text
            on error
                return
            end try
            tell application "Ghostty" to input text clipboardText to targetTerminal
            return
        end if
        display notification messageText with title "Remote image paste failed"
        error messageText number statusCode
    end try

    tell application "Ghostty" to input text remotePath to targetTerminal
end run