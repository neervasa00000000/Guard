#!/bin/sh
set -eu
kit=${1:?Pass the extracted review kit}
fonts=${2:?Pass the directory containing the verified font files}
pillow_docs=${3:?Pass the original test3_docs.json}
mode=${4:-replay}
work=${5:-"$kit/start-work"}
mkdir -p "$work"
out=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
docker run --rm --network none \
    --mount "type=bind,src=$work,dst=/work" \
    --mount "type=bind,src=$kit,dst=/kit,readonly" \
    --mount "type=bind,src=$fonts,dst=/fonts,readonly" \
    --mount "type=bind,src=$pillow_docs,dst=/test3_docs.json,readonly" \
    --mount "type=bind,src=$out,dst=/out" \
    --mount "type=bind,src=$(dirname "$out"),dst=/review,readonly" \
    --env "FORMS_MODE=$mode" guard-e1-review4-forms sh -euxc '
        mkdir -p /workspace/guard-paper/results /workspace/guard-paper/v5.7-ieee
        cp -a /kit/results/e1-full /workspace/guard-paper/results/
        src=/kit/v5.7-ieee/new_tests_renderer2
        dest=/workspace/guard-paper/v5.7-ieee/new_tests_renderer2
        cp -a "$src" "$dest"
        python -u /out/replay_checks.py setup "$src" "$dest"
        fc-cache -f
        soffice --version
        pdftoppm -v
        cd "$dest"
        if [ "$FORMS_MODE" = start ] || [ "$FORMS_MODE" = start-resume ]; then
            ln -s /work work
            if [ "$FORMS_MODE" = start ]; then
                python -u scripts/gen.py
                python -u /out/replay_checks.py inputs "$src" "$dest"
                PYTHONPATH="$dest/scripts" python -u /out/measure_tables.py
            fi
            cp /out/replayed_forms_obs.csv csv/forms_obs.csv
            cp /out/replayed_calib_obs.csv csv/calib_obs.csv
            python -u /out/replay_checks.py geometry "$src" "$dest"
            NW=6 python -u scripts/attack.py > /out/libreoffice_attack.log
            python -u /out/replay_checks.py hits "$src" "$dest" --primary-only
            PYTHONPATH="$dest/scripts:/review" python -u /out/start_padding.py "$src" "$dest"
            exit
        fi
        python -u scripts/gen.py
        python -u /out/replay_checks.py inputs "$src" "$dest"
        python -u /out/pillow_control.py
        NW=6 python -u scripts/measure.py
        python -u /out/replay_checks.py geometry "$src" "$dest"
        NW=6 python -u scripts/attack.py > /out/libreoffice_attack.log
        python -u /out/replay_checks.py hits "$src" "$dest" --primary-only
    '
