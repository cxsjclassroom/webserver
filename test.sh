export PYTHONPATH=$(cd `dirname $0`; pwd)/server:$(cd `dirname $0`; pwd)/thirdparty
python -B $(cd `dirname $0`; pwd)/test/test.py
