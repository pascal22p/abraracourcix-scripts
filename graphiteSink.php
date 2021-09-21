<?php
error_reporting(E_ALL);

$data = trim(file_get_contents('php://input'));

if(empty($data)) {
  echo "No content provided";
  http_response_code(400);
  exit();
}

$metrics = explode("\n", $data);

$fp = fsockopen("tcp://127.0.0.1", 2003, $errno, $errstr);
if (!empty($errno)) {
  echo $errno;
  http_response_code(500);
  exit();
}
if (!empty($errstr)) {
  echo $errstr;
  http_response_code(500);
  exit();
}

foreach($metrics as $data) {
  if (strpos($data, "***REMOVED***")===false) {
    echo "Not authorised";
    http_response_code(401);
    exit();
  } else {
    $data = str_replace("***REMOVED***", "", $data);
  }
     
  $pieces = explode(" ", trim($data));

  if (count($pieces) == 2) {
    $data = trim($data)." ".time().PHP_EOL;
  } else {
    $data = trim($data).PHP_EOL;
  }

  try {
      //$fp = fsockopen("tcp://127.0.0.1", 2003, $errno, $errstr);

      //if (!empty($errno)) echo $errno;
      //if (!empty($errstr)) echo $errstr;

      $bytes = fwrite($fp, $data);
      fflush($fp);
      if($bytes == strlen($data)) {
        echo $data;
      } else {
        echo "Size does not match";
        http_response_code(500);
        exit();
      }
  } catch (Exception $e) {
    echo "\nNetwork error: ".$e->getMessage();
    http_response_code(500);
    exit();
  }
}

fclose($fp);
echo "ALL GOOD";
http_response_code(202);
?>
