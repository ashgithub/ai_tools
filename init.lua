local log = hs.logger.new('TextProcessor', 'debug')

-- Paths
local dir = os.getenv("HOME") .. "/work/code/python/ai_tools"
local scriptPath = dir .. "/clients/multi_tool_client.py"
local refreshScriptPath = dir .. "/clients/refresh_model_cache_via_oci_cli.py"
-- local scriptMode = "-m proof"
local default_window_width = 900
local default_window_height = 800
local show_screen_debug_alert = true
local model_cache_path = dir .. "/.cache/oci_models_cache.json"
local model_cache_refresh_hours = 24

local terminal_config = {  -- Shared config for terminal-like apps (iTerm2, Code)
    copy = function()
        -- Enter iTerm2 copy mode with Cmd+Shift+C
        hs.eventtap.keyStroke({"cmd", "shift"}, "c")
        hs.timer.usleep(100000)
        
        -- In copy mode, use Shift+V to select entire line
        hs.eventtap.keyStroke({"shift"}, "v")
        hs.timer.usleep(100000)
        
        -- Press y to yank (copy) selection to system clipboard and exit copy mode
        hs.eventtap.keyStrokes("y")
        hs.timer.usleep(300000)
    end,
    paste = function()
        -- Send Escape first to ensure you're in normal mode
        hs.eventtap.keyStroke({}, "escape")
        hs.timer.usleep(50000)
        
        -- Use vi command: go to start, delete to end, enter insert mode
        hs.eventtap.keyStrokes("0d$i")
        hs.timer.usleep(50000)
        
        -- Paste from clipboard
        hs.eventtap.keyStroke({"cmd"}, "v")
        hs.timer.usleep(200000)
        hs.timer.usleep(200000)
        hs.eventtap.keyStroke({"cmd"}, "return")
        
        -- Exit insert mode
        --hs.eventtap.keyStroke({}, "escape")
        --hs.timer.usleep(50000)
    end
}

local app_configs = {
    ["Slack"] = {
        copy = function()
            hs.eventtap.keyStroke({"cmd"}, "a")
            hs.timer.usleep(300000)
            hs.eventtap.keyStroke({"cmd"}, "c")
            hs.timer.usleep(300000)
        end,
        paste = function()
            hs.eventtap.keyStroke({"cmd"}, "a")
            hs.timer.usleep(200000)
            hs.eventtap.keyStroke({"cmd"}, "v")
            hs.timer.usleep(200000)
            hs.eventtap.keyStroke({"cmd"}, "return")
        end
    },
    ["iTerm2"] = terminal_config,
    ["Code"] = terminal_config,
    ["default"] = {
        copy = function()
            hs.eventtap.keyStroke({"cmd"}, "c")
            hs.timer.usleep(300000)
        end,
        paste = function()
            hs.eventtap.keyStroke({"cmd"}, "v")
            hs.timer.usleep(200000)
        end
    }
}

local function clamp(value, min_value, max_value)
    if value < min_value then
        return min_value
    end
    if value > max_value then
        return max_value
    end
    return value
end

local function log_screen_strategy(strategy, screen)
    local screen_name = (screen and screen:name()) or "unknown"
    log.i(string.format("Window target strategy=%s screen=%s", strategy, screen_name))
    if show_screen_debug_alert then
        hs.alert.show(string.format("Screen target: %s (%s)", strategy, screen_name), 1)
    end
end

local function resolve_target_screen(trigger_window, trigger_app)
    if trigger_window then
        local window_screen = trigger_window:screen()
        if window_screen then
            return window_screen, "focusedWindow"
        end
    end

    if trigger_app then
        local main_window = trigger_app:mainWindow()
        if main_window then
            local main_screen = main_window:screen()
            if main_screen then
                return main_screen, "mainWindow"
            end
        end
    end

    local mouse_screen = hs.mouse.getCurrentScreen()
    if mouse_screen then
        return mouse_screen, "mouse"
    end

    local primary = hs.screen.primaryScreen()
    return primary, "primary"
end

local function build_window_args(trigger_window, trigger_app)
    local screen, strategy = resolve_target_screen(trigger_window, trigger_app)
    log_screen_strategy(strategy, screen)
    if not screen then
        return string.format("--window-width %d --window-height %d", default_window_width, default_window_height)
    end

    local frame = screen:frame()
    local max_x = frame.x + math.max(0, frame.w - default_window_width)
    local max_y = frame.y + math.max(0, frame.h - default_window_height)
    local centered_x = frame.x + ((frame.w - default_window_width) / 2)
    local centered_y = frame.y + ((frame.h - default_window_height) / 2)
    local window_x = math.floor(clamp(centered_x, frame.x, max_x))
    local window_y = math.floor(clamp(centered_y, frame.y, max_y))

    return string.format(
        "--window-width %d --window-height %d --window-x %d --window-y %d",
        default_window_width, default_window_height, window_x, window_y
    )
end

local function is_model_cache_stale()
    local attrs = hs.fs.attributes(model_cache_path)
    if not attrs then
        return true
    end
    local modified = attrs.modification
    if not modified then
        return true
    end
    local age_hours = (os.time() - modified) / 3600
    return age_hours >= model_cache_refresh_hours
end

local function ensure_model_cache()
    if not is_model_cache_stale() then
        return true
    end

    hs.alert.show("Refreshing model cache...", 1.5)
    local refresh_command = string.format(
        "cd %q && /opt/homebrew/bin/uv run %q 2>&1",
        dir, refreshScriptPath
    )
    local output, ok, _, rc = hs.execute(refresh_command, true)
    if not ok then
        local error_text = (output or ""):gsub("%s+$", "")
        local first_line = error_text:match("([^\n]+)") or "Unknown cache refresh error"
        log.e("Model cache refresh failed script=" .. refreshScriptPath .. " exit=" .. tostring(rc))
        log.e("refresh output:\n" .. (error_text ~= "" and error_text or "[No output]"))
        hs.alert.show("Model cache refresh failed: " .. refreshScriptPath .. "\n" .. first_line, 4)
        return false
    end
    return true
end

function processAppText()
    local trigger_window = hs.window.focusedWindow()
    local trigger_app = (trigger_window and trigger_window:application()) or hs.application.frontmostApplication()
    local appName = trigger_app and trigger_app:name() or ""
    local config = app_configs[appName] or app_configs["default"]
    local scriptMode = string.format("--app %q", appName)
    local windowArgs = build_window_args(trigger_window, trigger_app)

    if not ensure_model_cache() then
        return
    end

    hs.alert.show("Processing selected text from " .. appName .. "...")

    -- Save original clipboard
    local originalClipboard = hs.pasteboard.getContents()

    -- Copy selected text
    config.copy()
    hs.alert.show("text copied from " .. appName .. "...")
    hs.sound.getByName("Funk"):play()

    local text = hs.pasteboard.getContents()
    if not text or text == "" then
        hs.alert.show("No text was copied.")
    --     return
    end

    if text:find("EOF") then
        hs.alert.show("Text contains 'EOF'. Cannot safely use heredoc.")
        return
    end

    local heredoc = string.format(
        "cd %s && /opt/homebrew/bin/uv run %s %s %s <<'EOF'\n%s\nEOF",
        dir, scriptPath, scriptMode, windowArgs, text
    )
    hs.alert.show("Sending to AI Tools for processing...")

    local task = hs.task.new("/bin/zsh",
        function(exitCode, stdOut, stdErr)
            log.d("--- Python Output ---")
            log.d("Exit Code: " .. tostring(exitCode))
            log.d("stdout:\n" .. (stdOut or "[No stdout]"))
            log.d("stderr:\n" .. (stdErr or "[No stderr]"))

            if exitCode ~= 0 then
                local stderr_text = (stdErr or ""):gsub("%s+$", "")
                local first_line = stderr_text:match("([^\n]+)") or "Unknown error"
                log.e("Model/tool execution failed script=" .. scriptPath)
                log.e("stderr:\n" .. (stderr_text ~= "" and stderr_text or "[No stderr]"))
                hs.alert.show("Model catalog init failed: " .. scriptPath .. "\n" .. first_line, 4)
                return
            end

            if not stdOut or stdOut == "" then
                hs.alert.show("Python script returned no output.")
                return
            end

            hs.alert.show("Python script returned. Pasting output.")

            hs.pasteboard.setContents(stdOut)

            if trigger_app then
                trigger_app:activate()
            end
            hs.timer.usleep(200000)

            config.paste()
            hs.alert.show("text pasted from " .. appName .. "...")
            hs.sound.getByName("Funk"):play()

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
