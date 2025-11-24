local log = hs.logger.new('TextProcessor', 'debug')

-- Paths
local dir = os.getenv("HOME") .. "/work/code/python/ai_tools"
local scriptPath = dir .. "/clients/multi_tool_client.py"
-- local scriptMode = "-m proof"

function processAppText()
    local app = hs.application.frontmostApplication()
    local appName = app and app:name() or ""
    local scriptMode = "--app ".. "\"" .. appName .. "\""

--    if not (appName:match("Slack") or appName:match("Mail")) then
--        hs.alert.show("This hotkey only works in Slack or Mail.")
--        return
--    end

    hs.alert.show("Processing selected text from " .. appName .. "...")

    -- Save original clipboard
    local originalClipboard = hs.pasteboard.getContents()

    -- Copy selected text
    if appName:match("Slack") then
        hs.eventtap.keyStroke({ "cmd" }, "a")
        hs.timer.usleep(300000)
    end 
    hs.eventtap.keyStroke({ "cmd" }, "c")
    hs.timer.usleep(300000)

    local text = hs.pasteboard.getContents()
    if not text or text == "" then
        hs.alert.show("No text was copied.")
    --     return
    end

    if text:find("EOF") then
        hs.alert.show("Text contains 'EOF'. Cannot safely use heredoc.")
        return
    end

    local heredoc = string.format("cd %s && /opt/homebrew/bin/uv run %s %s <<'EOF'\n%s\nEOF", dir, scriptPath, scriptMode, text)
    hs.alert.show("Sending to AI Tools for processing...")

    local task = hs.task.new("/bin/zsh",
        function(exitCode, stdOut, stdErr)
            log.d("--- Python Output ---")
            log.d("Exit Code: " .. tostring(exitCode))
            log.d("stdout:\n" .. (stdOut or "[No stdout]"))
            log.d("stderr:\n" .. (stdErr or "[No stderr]"))

            if exitCode ~= 0 then
                hs.alert.show("Python script failed! Check logs.")
                return
            end

            if not stdOut or stdOut == "" then
                hs.alert.show("Python script returned no output.")
                return
            end

            hs.alert.show("Python script returned. Pasting output.")

            hs.pasteboard.setContents(stdOut)

            app:activate()
            hs.timer.usleep(200000)

            if appName:match("Slack") then
                hs.eventtap.keyStroke({ "cmd" }, "a")
                hs.timer.usleep(200000)
            end
            hs.eventtap.keyStroke({ "cmd" }, "v")
            hs.timer.usleep(200000)
            if appName:match("Slack") then
                hs.eventtap.keyStroke({ "cmd" }, "return")
                hs.alert.show("Slack text processed!")
            elseif appName:match("Mail") then
                hs.alert.show("Mail text processed – result copied.")
                hs.sound.getByName("Funk"):play()
            end

            -- Restore clipboard
            hs.timer.doAfter(0.5, function()
                hs.pasteboard.setContents(originalClipboard)
            end)
        end,
        { "-c", heredoc }
    )

    task:start()
end

 function urlDecode(str)
    str = str:gsub('+', ' ')  -- Convert '+' to space
    str = str:gsub('%%(%x%x)', function(hex)
        return string.char(tonumber(hex, 16))
    end)
    return str
end

-- Hotkey binding
hs.hotkey.bind({ "ctrl", "alt", "cmd" }, "\\", processAppText)

hs.alert.show("Text processor loaded – Ctrl+Alt+Cmd+\\", 3)

hs.urlevent.bind("alert", function(eventName, params)
    local message = urlDecode(params["msg"] )or "Hello from Shortcuts!"
    log.d("alert" .. message)
    hs.alert.show(message, 2)
    hs.sound.getByName("Blow"):play()
end)
